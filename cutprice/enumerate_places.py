"""1단계: 업소 목록 수집(싸다).

목록 엔드포인트는 한 요청에 수십 곳을 좌표까지 함께 준다.
전국 목록은 이 방식으로 수천 요청 규모에서 끝난다.
가격은 여기서 얻을 수 없다(대표가격만 오고, 그게 바로 문제의 원인).
"""

import argparse
import logging
import sys

from . import regions, store
from .naver import BudgetExhausted, Blocked, NaverPlace

log = logging.getLogger("enumerate")


def sweep(api, tree, level, max_pages):
    plan = regions.queries(tree, level)
    log.info("%s 단계: 질의 %d개", level, len(plan))
    pagination_ok = None
    total_new = 0

    for region, query in plan:
        seen, page = set(), 1
        collected = []
        while page <= max_pages:
            try:
                found = api.search(f"{query} 미용실", page=page)
            except (BudgetExhausted, Blocked) as exc:
                log.warning("중단: %s", exc)
                return total_new, False
            fresh = [f for f in found if f["id"] not in seen]
            if not found:
                break
            if page == 2 and pagination_ok is None:
                pagination_ok = bool(fresh)
                if not pagination_ok:
                    log.warning("page 파라미터가 먹지 않는다. 1페이지만 쓰고 "
                                "지역을 더 쪼개서 커버리지를 확보한다.")
            for f in fresh:
                seen.add(f["id"])
                collected.append(f)
                regions.learn(tree, f["region"])
            if not fresh or pagination_ok is False:
                break
            page += 1

        if collected:
            key = store.shard_key(region)
            added, size = store.upsert_places(key, region, collected)
            total_new += added
            log.info("%-22s +%-4d (누적 %d)", region, added, size)

    return total_new, True


def main(argv=None):
    parser = argparse.ArgumentParser(description="미용실 목록 수집")
    parser.add_argument("--level", choices=["sido", "sigungu", "dong"], default="sigungu")
    parser.add_argument("--budget", type=int, default=1200, help="이번 실행의 최대 요청 수")
    parser.add_argument("--delay", type=float, default=3.0, help="요청 간 최소 간격(초)")
    parser.add_argument("--max-pages", type=int, default=5)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    tree = regions.load()
    api = NaverPlace(delay=args.delay, budget=args.budget)

    try:
        new, finished = sweep(api, tree, args.level, args.max_pages)
    finally:
        regions.save(tree)
        store.rebuild_index()

    log.info("신규 %d곳 / 요청 %d회 / 지역트리 %s", new, api.used, regions.stats(tree))
    return 0 if finished else 1


if __name__ == "__main__":
    sys.exit(main())
