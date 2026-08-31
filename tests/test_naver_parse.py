"""네이버 응답 파싱 계층 테스트.

fixture는 2026-08-31에 실제로 받은 pcmap 응답의 구조를 그대로 줄인 것이다.
네이버가 구조를 바꾸면 여기가 먼저 깨진다.
"""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cutprice.menu import extract_cut_prices
from cutprice.naver import NaverPlace

PRICE_STATE = {
    "PlaceDetailBase:1276604203": {
        "__typename": "PlaceDetailBase", "id": "1276604203",
        "name": "샘플 미용실", "category": "미용실",
        "roadAddress": "서울 마포구 독막로5길 23 2층",
    },
    "Menu:1276604203_0": {
        "__typename": "Menu", "name": "앞머리컷", "price": "10,000원",
        "priceType": "cut", "id": "1276604203_0", "index": 0,
    },
    "Menu:1276604203_1": {
        "__typename": "Menu", "name": "전체 다운펌", "price": "50,000원",
        "priceType": "perm", "id": "1276604203_1", "index": 1,
    },
    "Menu:1276604203_8": {
        "__typename": "Menu", "name": "커트", "price": "36,000원",
        "priceType": "cut", "id": "1276604203_8", "index": 8,
    },
}

LIST_STATE = {
    "PlaceListBusinessesItem:1276604203": {
        "__typename": "PlaceListBusinessesItem", "id": "1276604203",
        "name": "샘플 미용실", "roadAddress": "독막로5길 23 2층",
        "address": "서교동 399-4", "commonAddress": "서울 마포구 서교동",
        "x": "126.9181972", "y": "37.5491208",
        "representativePrice": {
            "__typename": "RepresentativePrice", "priceName": "컷", "price": 36000,
        },
    },
    "PlaceListBusinessesItem:9999": {
        "__typename": "PlaceListBusinessesItem", "id": "9999",
        "name": "좌표없는집", "roadAddress": None, "address": None,
        "commonAddress": "서울 마포구 서교동", "x": None, "y": None,
        "representativePrice": None,
    },
    "Panorama:abc==": {"__typename": "Panorama"},
}


def page(state):
    return "<html><script>window.__APOLLO_STATE__ = %s;\n</script></html>" % json.dumps(
        state, ensure_ascii=False)


class TestApolloExtraction(unittest.TestCase):
    def test_menus_from_price_page(self):
        state = NaverPlace._apollo(page(PRICE_STATE))
        menus = [
            {"name": v["name"], "price": v["price"], "priceType": v["priceType"],
             "index": v["index"]}
            for k, v in state.items() if k.startswith("Menu:")
        ]
        self.assertEqual(len(menus), 3)
        cut = extract_cut_prices(menus)
        self.assertEqual(cut["w"]["price"], 36000)
        self.assertEqual(cut["w"]["src"], "커트")
        self.assertIn("앞머리컷", cut["dropped"])

    def test_broken_page_returns_empty(self):
        self.assertEqual(NaverPlace._apollo("<html>no state</html>"), {})
        self.assertEqual(NaverPlace._apollo(None), {})
        self.assertEqual(
            NaverPlace._apollo("<script>window.__APOLLO_STATE__ = {oops;\n</script>"), {})

    def test_list_items_and_coord_guard(self):
        state = NaverPlace._apollo(page(LIST_STATE))
        rows = []
        for key, item in state.items():
            if not key.startswith("PlaceListBusinessesItem:"):
                continue
            try:
                x, y = float(item["x"]), float(item["y"])
            except (TypeError, ValueError, KeyError):
                continue
            rows.append({"id": item["id"], "x": x, "y": y,
                         "region": item.get("commonAddress")})
        self.assertEqual(len(rows), 1)            # 좌표 없는 항목은 버린다
        self.assertEqual(rows[0]["id"], "1276604203")
        self.assertAlmostEqual(rows[0]["x"], 126.9181972)
        self.assertEqual(rows[0]["region"], "서울 마포구 서교동")


if __name__ == "__main__":
    unittest.main(verbosity=2)


class FakeResponse:
    def __init__(self, body, encoding):
        self._body = body
        self.encoding = encoding

    @property
    def text(self):
        # requests와 동일하게 self.encoding으로 디코딩한다
        return self._body.decode(self.encoding or "iso-8859-1")


class TestDecoding(unittest.TestCase):
    """네이버는 charset 헤더를 안 준다. UTF-8로 강제하지 않으면 한글이 깨진다."""

    def test_no_charset_header_is_read_as_utf8(self):
        body = "맨즈플랜헤어 노원역3호점".encode("utf-8")
        res = FakeResponse(body, "ISO-8859-1")        # requests의 기본 추정값
        self.assertEqual(NaverPlace._decode(res), "맨즈플랜헤어 노원역3호점")

    def test_explicit_charset_is_respected(self):
        body = "커트".encode("utf-8")
        res = FakeResponse(body, "utf-8")
        self.assertEqual(NaverPlace._decode(res), "커트")
