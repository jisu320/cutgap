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
from .menu import extract_cut_prices, is_cut_menu
from .naver import BudgetExhausted, Blocked, NaverPlace

log = logging.getLogger("refresh")


def apply_menus(place, menus):
    """메뉴 목록을 판정 결과와 함께 저장한다.

    커트로 분류된 메뉴는 이름/가격을 그대로 남긴다(cuts). 판정 규칙을
    고칠 때마다 다시 긁지 않고 reparse로 재판정할 수 있어야 하기 때문이다.
    펌·염색 등 커트가 아닌 메뉴는 저장하지 않는다.
    """
    cuts = [{"n": m.get("name"), "p": m.get("price")}
            for m in menus if is_cut_menu(m)]
    place["cuts"] = cuts
    result = extract_cut_prices(menus)
    place["w"] = result["w"]
    place["m"] = result["m"]
    return result


def as_menus(cuts):
    """저장된 cuts를 판정 함수가 먹는 형태로 되돌린다."""
    return [{"name": c.get("n"), "price": c.get("p"), "priceType": "cut", "index": i}
            for i, c in enumerate(cuts or [])]


def stalest(limit):
    """확인이 가장 오래된 순으로 (샤드키, 업소) 목록을 만든다.

    확인일이 같으면 메뉴가 아직 없는 곳(cuts 미저장)을 먼저 집는다.
    같은 날 중단된 작업을 이어받을 때 이미 끝낸 곳을 다시 긁지 않기 위한 것이다.
    """
    rows = []
    for key in store.all_shard_keys():
        for place in store.load_shard(key).get("places", []):
            has_menus = 1 if "cuts" in place else 0
            rows.append((place.get("checked") or "", has_menus, key, place["id"]))
    rows.sort()
    return [(checked, key, pid) for checked, _, key, pid in rows][:limit]


def main(argv=None):
    parser = argparse.ArgumentParser(description="커트 가격 갱신")
    parser.add_argument("--budget", type=int, default=2000, help="이번 실행의 최대 요청 수")
    parser.add_argument("--delay", type=float, default=3.0)
    parser.add_argument("--save-every", type=int, default=25,
                        help="이만큼 처리할 때마다 중간 저장한다")
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
    total = len(targets)
    for key, ids in by_shard.items():
        if stopped:
            break
        shard = store.load_shard(key)
        index = {p["id"]: p for p in shard.get("places", [])}
        dirty = 0
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
            dirty += 1
            done += 1
            if menus is None:
                place["gone"] = True
                failed += 1
            else:
                place.pop("gone", None)
                apply_menus(place, menus)
                if place["w"] or place["m"]:
                    priced += 1
            # 오래 도는 작업이라 중간에 죽어도 여기까지는 남는다
            if dirty >= args.save_every:
                store.save_shard(key, shard)
                dirty = 0
                log.info("  %d/%d 진행 (가격 확보 %d)", done, total, priced)
        if dirty:
            store.save_shard(key, shard)

    store.rebuild_index()
    log.info("확인 %d곳 / 가격 확보 %d곳 / 페이지 실패 %d곳 / 요청 %d회",
             done, priced, failed, api.used)
    return 0


if __name__ == "__main__":
    sys.exit(main())
