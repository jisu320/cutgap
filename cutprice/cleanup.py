"""검색이 물어온 타지역 업소를 샤드에서 걷어낸다.

소속 라벨(in)이 있는 업소는 응답이 그 지역 소속이라고 말한 것이므로 믿는다.
라벨이 없는 옛 데이터는 라벨 있는 업소들의 좌표 범위를 기준선으로 삼아
그 밖에 있으면 다른 지역 업소로 보고 뺀다. 행정경계 데이터 없이
샤드 자체 분포만 쓰기 때문에 어느 지역에나 그대로 적용된다.

    python -m cutprice.cleanup --dry-run
"""

import argparse
import sys

from . import store

MARGIN = 0.004      # 약 400m. 경계 근처 업소를 억울하게 빼지 않도록 여유를 둔다


def bbox(places, margin=MARGIN):
    xs = [p["x"] for p in places if "x" in p]
    ys = [p["y"] for p in places if "y" in p]
    if not xs:
        return None
    return (min(xs) - margin, max(xs) + margin, min(ys) - margin, max(ys) + margin)


def main(argv=None):
    parser = argparse.ArgumentParser(description="타지역 업소 정리")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    total_out = 0
    for key in store.all_shard_keys():
        shard = store.load_shard(key)
        places = shard.get("places", [])
        region = shard.get("region", key)
        labeled = [p for p in places if p.get("in")]
        if len(labeled) < 20:
            print("%-16s 라벨 %d곳뿐이라 기준선을 못 만든다. 건너뜀"
                  % (region, len(labeled)))
            continue
        box = bbox(labeled)
        lo, hi, la, ha = box

        keep, drop, suspect = [], [], []
        for p in places:
            label = p.get("in")
            if label:
                # 라벨이 있으면 그게 정답이다. 다르면 확정적으로 뺀다.
                (keep if label.startswith(region) else drop).append(p)
                continue
            keep.append(p)
            inside = lo <= p.get("x", 0) <= hi and la <= p.get("y", 0) <= ha
            if not inside:
                suspect.append(p)

        if suspect:
            print("%-16s 소속 미확정 + 좌표 이상 %d곳 (지우지 않고 표시만)"
                  % (region, len(suspect)))
            for p in suspect[:5]:
                print("     확인 필요: %-22s %s"
                      % (p.get("name", "")[:22], p.get("road", "")))

        if not drop:
            print("%-16s %d곳 유지 (라벨 불일치 없음)" % (region, len(places)))
            continue

        total_out += len(drop)
        print("%-16s %d곳 -> %d곳 (타지역 %d곳 제외)"
              % (region, len(places), len(keep), len(drop)))
        print("     기준 범위 lon %.4f~%.4f / lat %.4f~%.4f" % box)
        for p in drop[:6]:
            print("     빼는 곳: %-22s %s" % (p.get("name", "")[:22], p.get("road", "")))
        if len(drop) > 6:
            print("     ... 외 %d곳" % (len(drop) - 6))

        if not args.dry_run:
            shard["places"] = keep
            store.save_shard(key, shard)

    if not args.dry_run:
        store.rebuild_index()
    print("\n합계 %d곳 제외%s" % (total_out, " [dry-run]" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
