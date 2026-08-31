"""저장된 커트 메뉴에 판정 규칙을 다시 적용한다. 네트워크를 쓰지 않는다.

`cutprice/menu.py`의 규칙(EXCLUDE / FEMALE / MALE)을 고친 뒤 이걸 돌리면
재수집 없이 전체 데이터의 가격 판정이 갱신된다.

    python -m cutprice.reparse            # 실제로 반영
    python -m cutprice.reparse --dry-run  # 무엇이 바뀌는지만 본다
"""

import argparse
import sys

from . import store
from .menu import extract_cut_prices
from .refresh_prices import as_menus


def main(argv=None):
    parser = argparse.ArgumentParser(description="저장된 메뉴로 재판정")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--show", type=int, default=20, help="변경 사례 표시 개수")
    args = parser.parse_args(argv)

    changed = skipped = 0
    samples = []

    for key in store.all_shard_keys():
        shard = store.load_shard(key)
        dirty = False
        for place in shard.get("places", []):
            cuts = place.get("cuts")
            if cuts is None:
                skipped += 1
                continue
            before = (place.get("w"), place.get("m"))
            result = extract_cut_prices(as_menus(cuts))
            after = (result["w"], result["m"])
            if before != after:
                changed += 1
                if len(samples) < args.show:
                    samples.append((place.get("name"), before, after))
                place["w"] = result["w"]
                place["m"] = result["m"]
                dirty = True
        if dirty and not args.dry_run:
            store.save_shard(key, shard)

    if not args.dry_run:
        store.rebuild_index()

    def fmt(cut):
        return "없음" if not cut else "%s원(%s)" % (format(cut["price"], ","), cut["src"])

    print("재판정 결과: 변경 %d곳 / 메뉴 미저장으로 건너뜀 %d곳%s"
          % (changed, skipped, " [dry-run]" if args.dry_run else ""))
    if skipped:
        print("  건너뛴 곳은 cuts 필드가 없다. refresh_prices를 한 번 더 돌려야 한다.")
    for name, before, after in samples:
        print("  %s" % name)
        print("      여 %s -> %s" % (fmt(before[0]), fmt(after[0])))
        print("      남 %s -> %s" % (fmt(before[1]), fmt(after[1])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
