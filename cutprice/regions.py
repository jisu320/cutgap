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

# 시도 단위 검색은 한 번에 58건만 주기 때문에, 그 결과만으로는 산하
# 시군구를 다 알아낼 수 없다(서울에서 7개만 나왔다). 그래서 수집 대상
# 시도의 시군구는 목록으로 심어준다. 동 이름은 그대로 자동 학습한다.
SEED_SIGUNGU = {
    "서울": [
        "강남구", "강동구", "강북구", "강서구", "관악구", "광진구", "구로구",
        "금천구", "노원구", "도봉구", "동대문구", "동작구", "마포구", "서대문구",
        "서초구", "성동구", "성북구", "송파구", "양천구", "영등포구", "용산구",
        "은평구", "종로구", "중구", "중랑구",
    ],
    "경기": [
        "가평군", "고양시", "과천시", "광명시", "광주시", "구리시", "군포시",
        "김포시", "남양주시", "동두천시", "부천시", "성남시", "수원시", "시흥시",
        "안산시", "안성시", "안양시", "양주시", "양평군", "여주시", "연천군",
        "오산시", "용인시", "의왕시", "의정부시", "이천시", "파주시", "평택시",
        "포천시", "하남시", "화성시",
    ],
}

PATH = os.path.join(store.DATA, "regions.json")


def load():
    tree = store.read_json(PATH)
    if not tree:
        tree = {sido: {} for sido in SEEDS}
    for sido in SEEDS:
        tree.setdefault(sido, {})
    for sido, sigungus in SEED_SIGUNGU.items():
        for sigungu in sigungus:
            tree[sido].setdefault(sigungu, [])
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


def queries(tree, level, sido_filter=None):
    """검색에 쓸 질의 문자열 목록.

    level='sido'    씨앗 단계. 시군구를 알아내기 위한 정찰.
    level='sigungu' 시군구 단위. 동을 알아내면서 업소도 대량 확보.
    level='dong'    동 단위. 실제 전수 수집.

    sido_filter를 주면 그 시도만 다룬다. 예: ["서울", "경기"]
    """
    out = []
    wanted = set(sido_filter) if sido_filter else None
    if level == "sido":
        return [(s, s) for s in SEEDS if not wanted or s in wanted]
    for sido, sigungus in sorted(tree.items()):
        if wanted and sido not in wanted:
            continue
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


def stats(tree, sido_filter=None):
    wanted = set(sido_filter) if sido_filter else set(tree)
    sub = {k: v for k, v in tree.items() if k in wanted}
    sigungu = sum(len(v) for v in sub.values())
    dong = sum(len(d) for v in sub.values() for d in v.values())
    return {"sido": len(sub), "sigungu": sigungu, "dong": dong}
