"""1단계: 업소 목록 수집(싸다).

목록 엔드포인트는 한 요청에 수십 곳을 좌표까지 함께 준다.
전국 목록은 이 방식으로 수천 요청 규모에서 끝난다.
가격은 여기서 얻을 수 없다(대표가격만 오고, 그게 바로 문제의 원인).
"""

import argparse
import logging
import os
import sys
from datetime import date, timedelta

from . import regions, store
from .naver import BudgetExhausted, Blocked, NaverPlace

log = logging.getLogger("enumerate")

# 목록 응답은 한 질의당 58건에서 잘린다(page 파라미터도 안 먹는다).
# 그래서 같은 지역을 검색어만 바꿔 여러 번 물어보고 결과를 합친다.
KEYWORDS = ["미용실", "헤어샵", "헤어", "바버샵", "커트",
            "미용", "헤어살롱", "미장원", "이용원", "이발관", "살롱", "뷰티"]

# 어느 (지역, 검색어) 조합을 언제 훑었는지 기록한다. 하루 예산으로 끊고
# 다음 날 이어받기 위한 것. 이게 없으면 매일 같은 질의만 반복한다.
STATE = os.path.join(store.DATA, "enum_state.json")


def plan_for(tree, level, query, refine, sido=None):
    """검색 질의 목록을 만든다. --query가 있으면 그 지역만 다룬다."""
    if not query:
        return regions.queries(tree, level, sido)
    plan = [(query, query)]
    if refine:
        parts = query.split()
        dongs = []
        if len(parts) >= 2:
            dongs = tree.get(parts[0], {}).get(parts[1], [])
        plan += [(query, "%s %s" % (query, d)) for d in dongs]
    return plan


def sweep(api, tree, level, max_pages, query=None, refine=False, keywords=None,
          sido=None, restale=30):
    plan = plan_for(tree, level, query, refine, sido)
    keywords = keywords or ["미용실"]
    log.info("질의 %d개 × 검색어 %d개 (%s)", len(plan), len(keywords), query or level)
    pagination_ok = None
    total_new = 0

    state = load_state()
    today = date.today().isoformat()
    skipped = 0

    for region, area in plan:
        seen = set()
        collected = []
        for keyword in keywords:
            if is_fresh(state, area, keyword, restale):
                skipped += 1
                continue
            page = 1
            while page <= max_pages:
                try:
                    found = api.search(f"{area} {keyword}", page=page)
                except (BudgetExhausted, Blocked) as exc:
                    log.warning("중단: %s (다음 실행이 여기서 이어받는다)", exc)
                    if collected:
                        added, size = _flush(region, collected)
                        total_new += added
                        log.info("%-26s +%-4d (누적 %d)", area, added, size)
                    save_state(state)
                    return total_new, False
                found = [f for f in found if belongs(f, region)]
                fresh = [f for f in found if f["id"] not in seen]
                if not found:
                    break
                if page == 2 and pagination_ok is None:
                    pagination_ok = bool(fresh)
                    if not pagination_ok:
                        log.warning("page 파라미터가 먹지 않는다. 1페이지만 쓰고 "
                                    "지역·검색어를 쪼개서 커버리지를 확보한다.")
                for f in fresh:
                    seen.add(f["id"])
                    collected.append(f)
                    regions.learn(tree, f["region"])
                if not fresh or pagination_ok is False:
                    break
                page += 1
            state["%s|%s" % (area, keyword)] = today

        if collected:
            added, size = _flush(region, collected)
            total_new += added
            log.info("%-26s +%-4d (누적 %d)", area, added, size)

    save_state(state)
    if skipped:
        log.info("최근 %d일 내 훑은 질의 %d개는 건너뜀", restale, skipped)
    return total_new, True


def load_state():
    return store.read_json(STATE, default={}) or {}


def save_state(state):
    store.write_json(STATE, state)


def is_fresh(state, area, keyword, days):
    """이 질의를 최근 days일 안에 이미 훑었나. days<=0이면 항상 다시 훑는다."""
    if days <= 0:
        return False
    seen = state.get("%s|%s" % (area, keyword))
    if not seen:
        return False
    return seen >= (date.today() - timedelta(days=days - 1)).isoformat()


def belongs(item, region):
    """검색 결과가 대상 지역 소속인가.

    '서울 노원구 미용실'로 검색해도 인접 구(성북·강북·중랑) 업소가 섞여 온다.
    응답의 commonAddress로 걸러낸다. 소속을 못 읽으면 버린다.
    """
    where = item.get("region") or ""
    return where.startswith(region)


def _flush(region, collected):
    key = store.shard_key(region)
    return store.upsert_places(key, region, collected)


def main(argv=None):
    parser = argparse.ArgumentParser(description="미용실 목록 수집")
    parser.add_argument("--level", choices=["sido", "sigungu", "dong"], default="sigungu")
    parser.add_argument("--budget", type=int, default=1200, help="이번 실행의 최대 요청 수")
    parser.add_argument("--delay", type=float, default=3.0, help="요청 간 최소 간격(초)")
    parser.add_argument("--max-pages", type=int, default=5)
    parser.add_argument("--query", help='지역 하나만 수집. 예: "서울 노원구"')
    parser.add_argument("--refine", action="store_true",
                        help="--query 지역에서 이미 알아낸 동까지 쪼개서 수집")
    parser.add_argument("--keywords", default="미용실",
                        help='쉼표로 구분. "all"이면 %s' % ",".join(KEYWORDS))
    parser.add_argument("--sido", default="서울,경기",
                        help='수집 대상 시도. 쉼표로 구분. "all"이면 전국')
    parser.add_argument("--restale", type=int, default=30,
                        help="이 일수 안에 이미 훑은 질의는 건너뛴다. 0이면 전부 다시")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    tree = regions.load()
    api = NaverPlace(delay=args.delay, budget=args.budget)
    sido = None if args.sido == "all" else [
        x.strip() for x in args.sido.split(",") if x.strip()]

    try:
        keywords = KEYWORDS if args.keywords == "all" else [
            k.strip() for k in args.keywords.split(",") if k.strip()]
        new, finished = sweep(api, tree, args.level, args.max_pages,
                              query=args.query, refine=args.refine,
                              keywords=keywords, sido=sido, restale=args.restale)
    finally:
        regions.save(tree)
        store.rebuild_index()

    log.info("신규 %d곳 / 요청 %d회 / 지역트리 %s",
             new, api.used, regions.stats(tree, sido))
    return 0 if finished else 1


if __name__ == "__main__":
    sys.exit(main())
