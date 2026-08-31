"""네이버 플레이스 접근 계층.

수집량을 최소화하는 것이 이 파일의 목적이다.
 - 요청 간격 기본 3초 + 지터
 - 429를 받으면 길게 물러선다(네이버는 짧은 버스트에도 바로 429를 준다)
 - 하루 요청 예산을 넘기면 스스로 멈춘다
 - 원문을 저장하지 않는다. 필요한 필드만 뽑고 버린다

엔드포인트는 비공식이라 언제든 바뀔 수 있다.
바뀌면 이 파일 하나만 고치면 되도록 나머지 코드와 분리해 두었다.
2026-08-31 기준 응답 구조를 확인하고 작성했다.
"""

import json
import logging
import random
import re
import time

import requests

LIST_URL = "https://pcmap.place.naver.com/hairshop/list"
PRICE_URL = "https://pcmap.place.naver.com/hairshop/{place_id}/price"

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

_APOLLO = re.compile(r"window\.__APOLLO_STATE__\s*=\s*(\{.*?\});\s*\n", re.S)

log = logging.getLogger(__name__)


class BudgetExhausted(Exception):
    """하루 요청 예산을 다 썼다. 정상 종료 신호로 쓴다."""


class Blocked(Exception):
    """반복 429 등으로 더 요청하면 안 되는 상태."""


class NaverPlace:
    def __init__(self, delay=3.0, budget=2500, timeout=15, max_retries=4):
        self.delay = delay
        self.budget = budget
        self.used = 0
        self.timeout = timeout
        self.max_retries = max_retries
        self._last = 0.0
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": UA,
            "Referer": "https://map.naver.com/",
            "Accept-Language": "ko-KR,ko;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        })

    # ── 저수준 ────────────────────────────────────────────
    def _wait(self):
        gap = time.monotonic() - self._last
        need = self.delay + random.uniform(0, self.delay * 0.4)
        if gap < need:
            time.sleep(need - gap)

    def _get(self, url, params=None):
        if self.used >= self.budget:
            raise BudgetExhausted(f"요청 예산 {self.budget}회 소진")
        backoff = 60.0
        for attempt in range(self.max_retries):
            self._wait()
            self.used += 1
            self._last = time.monotonic()
            try:
                res = self.session.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as exc:
                log.warning("요청 실패(%s) %s", exc, url)
                time.sleep(5)
                continue
            if res.status_code == 200:
                return res.text
            if res.status_code == 429:
                log.warning("429. %.0f초 대기 후 재시도 (%d/%d)",
                            backoff, attempt + 1, self.max_retries)
                time.sleep(backoff)
                backoff *= 2
                continue
            if res.status_code in (403, 404, 410):
                log.info("HTTP %s %s", res.status_code, url)
                return None
            log.warning("HTTP %s %s", res.status_code, url)
            time.sleep(10)
        raise Blocked(f"{self.max_retries}회 재시도 실패: {url}")

    @staticmethod
    def _apollo(html):
        if not html:
            return {}
        m = _APOLLO.search(html)
        if not m:
            return {}
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            log.warning("APOLLO_STATE 파싱 실패")
            return {}

    # ── 목록: 한 요청에 수십 곳. 좌표까지 같이 온다 ─────────
    def search(self, query, page=1):
        """지역명 질의 -> 업소 목록. 좌표(x, y)는 WGS84."""
        html = self._get(LIST_URL, {"query": query, "page": page})
        state = self._apollo(html)
        out = []
        for key, item in state.items():
            if not key.startswith("PlaceListBusinessesItem:"):
                continue
            try:
                x = float(item["x"])
                y = float(item["y"])
            except (TypeError, ValueError, KeyError):
                continue
            rep = item.get("representativePrice") or {}
            out.append({
                "id": str(item.get("id") or key.split(":", 1)[1]),
                "name": item.get("name"),
                "road": item.get("roadAddress"),
                "addr": item.get("address"),
                "region": item.get("commonAddress"),
                "x": x,
                "y": y,
                "rep": {
                    "name": rep.get("priceName"),
                    "price": rep.get("price"),
                } if rep.get("priceName") else None,
            })
        return out

    # ── 상세: 업소당 1요청. 여기서만 메뉴 전체를 볼 수 있다 ──
    def menus(self, place_id):
        """업소의 메뉴 목록. 페이지가 없거나 메뉴가 없으면 빈 리스트."""
        html = self._get(PRICE_URL.format(place_id=place_id))
        state = self._apollo(html)
        if not state:
            return None                      # 페이지 자체를 못 읽음
        found = []
        for key, item in state.items():
            if key.startswith("Menu:"):
                found.append({
                    "name": item.get("name"),
                    "price": item.get("price"),
                    "priceType": item.get("priceType"),
                    "index": item.get("index", 0),
                })
        found.sort(key=lambda m: m["index"])
        return found
