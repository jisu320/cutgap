"""2단계: 가격 갱신(비싸다).

업소당 1요청이 필요하고 전국이 10만 곳대라, 하루 예산만큼
'가장 오래 확인 안 된 곳'부터 돌린다. 예산을 전체/60 정도로 두면
2달에 한 바퀴가 돈다.
"""

import argparse
import logging
import sys
from datetime import date

from . import store
from .menu import extract_cut_prices
from .naver import BudgetExhausted, Blocked, NaverPlace

log = logging.getLogger("refresh")


def stalest(limit):
    """확인이 가장 오래된 순으로 (샤드키, 업소) 목록을 만든다."""
    rows = []
    for key in store.all_shard_keys():
        for place in store.load_shard(key).get("places", []):
            rows.append((place.get("checked") or "", key, place["id"]))
    rows.sort()
    return rows[:limit]


def main(argv=None):
    parser = argparse.ArgumentParser(description="커트 가격 갱신")
    parser.add_argument("--budget", type=int, default=2000, help="이번 실행의 최대 요청 수")
    parser.add_argument("--delay", type=float, default=3.0)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    targets = stalest(args.budget)
    if not targets:
        log.info("갱신 대상이 없다. 먼저 enumerate_places를 돌려라.")
        return 0

    log.info("대상 %d곳 (가장 오래된 확인일: %s)", len(targets), targets[0][0] or "없음")
    api = NaverPlace(delay=args.delay, budget=args.budget + 20)
    today = date.today().isoformat()

    # 샤드 단위로 묶어 파일 쓰기를 줄인다.
    by_shard = {}
    for _, key, place_id in targets:
        by_shard.setdefault(key, []).append(place_id)

    done = priced = failed = 0
    stopped = False
    for key, ids in by_shard.items():
        if stopped:
            break
        shard = store.load_shard(key)
        index = {p["id"]: p for p in shard.get("places", [])}
        dirty = False
        for place_id in ids:
            place = index.get(place_id)
            if place is None:
                continue
            try:
                menus = api.menus(place_id)
            except (BudgetExhausted, Blocked) as exc:
                log.warning("중단: %s", exc)
                stopped = True
                break
            place["checked"] = today
            dirty = True
            done += 1
            if menus is None:
                place["gone"] = True
                failed += 1
                continue
            place.pop("gone", None)
            cut = extract_cut_prices(menus)
            place["w"] = cut["w"]
            place["m"] = cut["m"]
            if cut["w"] or cut["m"]:
                priced += 1
        if dirty:
            store.save_shard(key, shard)

    store.rebuild_index()
    log.info("확인 %d곳 / 가격 확보 %d곳 / 페이지 실패 %d곳 / 요청 %d회",
             done, priced, failed, api.used)
    return 0


if __name__ == "__main__":
    sys.exit(main())
