"""네이버 대표가격 vs 우리가 판정한 커트 가격을 비교한다.

'가격순 정렬이 앞머리컷 값으로 된다'는 문제가 실제로 얼마나 흔한지
수집한 데이터로 직접 세어보는 용도다. 규칙을 손볼 근거로 쓴다.

    python -m cutprice.audit
"""

import sys
from collections import Counter

from . import store


def main():
    rep_only = same = cheaper_rep = pricier_rep = no_cut = 0
    rep_names = Counter()
    examples = []

    for key in store.all_shard_keys():
        for p in store.load_shard(key).get("places", []):
            if not p.get("checked"):
                continue
            rep = p.get("rep") or {}
            rep_price = rep.get("price")
            rep_names[rep.get("name")] += 1
            cuts = [c["price"] for c in (p.get("w"), p.get("m")) if c]
            if not cuts:
                no_cut += 1
                continue
            ours = min(cuts)
            if rep_price is None:
                rep_only += 1
            elif rep_price == ours:
                same += 1
            elif rep_price < ours:
                cheaper_rep += 1
                if len(examples) < 15:
                    examples.append((p.get("name"), rep.get("name"), rep_price, ours,
                                     (p.get("w") or p.get("m") or {}).get("src")))
            else:
                pricier_rep += 1

    total = same + cheaper_rep + pricier_rep
    if not total:
        print("비교할 데이터가 없다. refresh_prices를 먼저 돌려라.")
        return 1

    print("대표가격과 비교 가능한 업소: %d곳" % total)
    print("  일치            %6d (%.1f%%)" % (same, 100 * same / total))
    print("  대표가격이 더 쌈 %6d (%.1f%%)  <- 부분컷이 대표로 잡힌 의심 사례"
          % (cheaper_rep, 100 * cheaper_rep / total))
    print("  대표가격이 더 비쌈%6d (%.1f%%)" % (pricier_rep, 100 * pricier_rep / total))
    print("  커트 메뉴 없음    %6d" % no_cut)
    print("\n대표가격 메뉴명 분포 상위:")
    for name, n in rep_names.most_common(10):
        print("  %-14s %d" % (name, n))
    if examples:
        print("\n대표가격이 더 싼 사례 (가게 / 대표메뉴 / 대표가 / 우리판정 / 근거메뉴):")
        for row in examples:
            print("  %s | %s %s | %s %s" % row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
