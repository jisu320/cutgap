"""수집 전에 사이트를 확인할 수 있게 예시 데이터를 만든다.

여기 나오는 가게 이름과 가격은 전부 지어낸 값이다. 실제 업소와 무관하다.
실제 수집을 시작하면 이 샤드는 지워라: python -m cutprice.make_sample --clear
"""

import argparse
import os
from datetime import date

from . import store

KEY = "예시_데이터"

SAMPLE = [
    ("리프컷 살롱",     "서울 마포구 독막로 1",  126.9138, 37.5490, 12000, 10000, "여성커트", "남성커트", "exact"),
    ("무드헤어 합정",   "서울 마포구 독막로 12", 126.9165, 37.5502, 15000, 13000, "여자컷", "남자컷", "exact"),
    ("스튜디오 여백",   "서울 마포구 양화로 30", 126.9122, 37.5478, 22000, None,  "레이디스 커트", None, "exact"),
    ("브릿지 살롱",     "서울 마포구 어울마당로 5", 126.9201, 37.5525, 18000, 15000, "커트(여)", "커트(남)", "exact"),
    ("온도 헤어",       "서울 마포구 월드컵로 9", 126.9090, 37.5551, 25000, 20000, "우먼 컷", "맨즈 컷", "exact"),
    ("화이트룸 미용실", "서울 마포구 신촌로 22", 126.9250, 37.5540, 13000, 13000, "커트", "커트", "neutral"),
    ("결 헤어살롱",     "서울 마포구 대흥로 8",  126.9430, 37.5480, None,  None,  None, None, None),
    ("노말 바버",       "서울 마포구 백범로 14", 126.9480, 37.5430, None,  18000, None, "커트", "exact"),
    ("청담라인 마포",   "서울 마포구 마포대로 3", 126.9455, 37.5395, 38000, 30000, "디자이너 커트(여)", "디자이너 커트(남)", "exact"),
    ("매일헤어",        "서울 마포구 성산로 40", 126.9105, 37.5595, 16000, 14000, "여성 커트", "남성 커트", "exact"),
]


def build():
    today = date.today().isoformat()
    places = []
    for i, (name, road, x, y, wp, mp, ws, ms, how) in enumerate(SAMPLE):
        places.append({
            "id": "sample-%02d" % i,
            "name": name,
            "road": road,
            "x": x,
            "y": y,
            "checked": today,
            "rep": {"name": "앞머리컷", "price": 8000},
            "w": {"price": wp, "src": ws, "how": how} if wp else None,
            "m": {"price": mp, "src": ms, "how": how} if mp else None,
        })
    store.save_shard(KEY, {"region": "예시 데이터 (서울 마포구)", "listed": today, "places": places})
    store.rebuild_index()
    print("예시 샤드 %d곳 작성. docs/ 를 정적 서버로 띄워 확인해라." % len(places))


def clear():
    path = os.path.join(store.PLACES, KEY + ".json")
    if os.path.exists(path):
        os.remove(path)
        print("예시 샤드 삭제")
    store.rebuild_index()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--clear", action="store_true")
    args = parser.parse_args()
    clear() if args.clear else build()
