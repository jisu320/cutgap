"""지역 목록을 스스로 알아낸다.

전국 시군구·읍면동 표를 코드에 박아두면 틀리거나 낡는다.
그래서 시도 17개만 씨앗으로 두고, 검색 결과에 들어 있는
commonAddress('서울 마포구 서교동')를 모아 지역 트리를 키운다.
"""

import os

from . import store

SEEDS = [
    "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
    "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주",
]

PATH = os.path.join(store.DATA, "regions.json")


def load():
    tree = store.read_json(PATH)
    if not tree:
        tree = {sido: {} for sido in SEEDS}
    for sido in SEEDS:
        tree.setdefault(sido, {})
    return tree


def save(tree):
    store.write_json(PATH, tree)


def learn(tree, common_address):
    """'서울 마포구 서교동' -> 트리에 시군구/동을 등록. 새로 배운 게 있으면 True."""
    if not common_address:
        return False
    parts = common_address.split()
    if len(parts) < 2:
        return False
    sido, sigungu = parts[0], parts[1]
    if sido not in tree:
        return False
    dongs = tree[sido].setdefault(sigungu, [])
    if len(parts) >= 3:
        dong = parts[2]
        if dong not in dongs:
            dongs.append(dong)
            dongs.sort()
            return True
        return False
    return sigungu not in tree[sido] or True


def queries(tree, level):
    """검색에 쓸 질의 문자열 목록.

    level='sido'    씨앗 단계. 시군구를 알아내기 위한 정찰.
    level='sigungu' 시군구 단위. 동을 알아내면서 업소도 대량 확보.
    level='dong'    동 단위. 실제 전수 수집.
    """
    out = []
    if level == "sido":
        return [(s, s) for s in SEEDS]
    for sido, sigungus in sorted(tree.items()):
        for sigungu, dongs in sorted(sigungus.items()):
            region = f"{sido} {sigungu}"
            if level == "sigungu":
                out.append((region, region))
            elif level == "dong":
                if dongs:
                    out.extend((region, f"{region} {d}") for d in dongs)
                else:
                    out.append((region, region))
    return out


def stats(tree):
    sigungu = sum(len(v) for v in tree.values())
    dong = sum(len(d) for v in tree.values() for d in v.values())
    return {"sido": len(tree), "sigungu": sigungu, "dong": dong}
