import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cutprice.menu import extract_cut_prices, gender_of, parse_price


def menu(name, price, ptype="cut"):
    return {"name": name, "price": price, "priceType": ptype}


class TestParsePrice(unittest.TestCase):
    def test_comma_and_won(self):
        self.assertEqual(parse_price("36,000원"), 36000)
        self.assertEqual(parse_price("10,000원~"), 10000)
        self.assertEqual(parse_price("15,000원 부터"), 15000)

    def test_no_number(self):
        self.assertIsNone(parse_price("가격문의"))
        self.assertIsNone(parse_price(None))
        self.assertIsNone(parse_price(""))

    def test_out_of_range(self):
        self.assertIsNone(parse_price("500원"))
        self.assertIsNone(parse_price("9,999,999원"))

    def test_already_number(self):
        self.assertEqual(parse_price(36000), 36000)


class TestGender(unittest.TestCase):
    def test_female(self):
        for name in ("여성커트", "여자컷", "우먼 컷", "레이디스 커트", "Women's Cut"):
            self.assertEqual(gender_of(name), "w", name)

    def test_male(self):
        for name in ("남성커트", "남자컷", "맨즈 컷", "신사 커트", "MEN CUT"):
            self.assertEqual(gender_of(name), "m", name)

    def test_neutral(self):
        for name in ("커트", "디자이너 커트", "남녀공용 커트", "여성/남성 커트"):
            self.assertIsNone(gender_of(name), name)


class TestExtract(unittest.TestCase):
    def test_real_case_from_naver(self):
        """실측 데이터. 대표가격이 '앞머리컷 10,000원'으로 잡혀 있던 가게."""
        menus = [
            menu("앞머리컷", "10,000원"),
            menu("전체 다운펌", "50,000원", "perm"),
            menu("뿌리염색 (3cm)", "88,000원", "color"),
            menu("크리닉", "60,000원", "clinic"),
            menu("커트", "36,000원"),
        ]
        got = extract_cut_prices(menus)
        self.assertEqual(got["w"]["price"], 36000)
        self.assertEqual(got["w"]["src"], "커트")
        self.assertEqual(got["w"]["how"], "neutral")
        self.assertEqual(got["m"]["price"], 36000)
        self.assertIn("앞머리컷", got["dropped"])

    def test_gendered_menus_win_over_neutral(self):
        menus = [
            menu("커트", "30,000원"),
            menu("여성커트", "25,000원"),
            menu("남성커트", "18,000원"),
        ]
        got = extract_cut_prices(menus)
        self.assertEqual((got["w"]["price"], got["w"]["how"]), (25000, "exact"))
        self.assertEqual((got["m"]["price"], got["m"]["how"]), (18000, "exact"))

    def test_cheapest_wins_within_gender(self):
        menus = [
            menu("여성커트", "25,000원"),
            menu("여성커트+샴푸", "30,000원"),
            menu("여자컷", "22,000원"),
        ]
        got = extract_cut_prices(menus)
        self.assertEqual(got["w"]["price"], 22000)

    def test_bang_variants_excluded(self):
        menus = [
            menu("앞머리 컷", "5,000원"),
            menu("시스루뱅", "8,000원"),
            menu("옆머리 정리", "6,000원"),
            menu("학생컷", "12,000원"),
            menu("삭발", "10,000원"),
            menu("여성커트", "24,000원"),
        ]
        got = extract_cut_prices(menus)
        self.assertEqual(got["w"]["price"], 24000)
        self.assertEqual(len(got["dropped"]), 5)

    def test_non_cut_types_ignored(self):
        menus = [
            menu("디자인펌", "150,000원", "perm"),
            menu("염색", "150,000원", "color"),
        ]
        got = extract_cut_prices(menus)
        self.assertIsNone(got["w"])
        self.assertIsNone(got["m"])
        self.assertEqual(got["dropped"], [])

    def test_missing_price_type_falls_back_to_name(self):
        menus = [
            {"name": "남성 커트", "price": "15,000원"},
            {"name": "매직 스트레이트", "price": "120,000원"},
        ]
        got = extract_cut_prices(menus)
        self.assertEqual(got["m"]["price"], 15000)
        self.assertEqual(got["m"]["how"], "exact")
        self.assertIsNone(got["w"])   # 중립 후보가 없으니 여성가는 비운다

    def test_price_inquiry_only(self):
        menus = [menu("커트", "가격문의")]
        got = extract_cut_prices(menus)
        self.assertIsNone(got["w"])
        self.assertIn("커트", got["dropped"])

    def test_empty(self):
        got = extract_cut_prices([])
        self.assertEqual(got, {"w": None, "m": None, "dropped": []})


if __name__ == "__main__":
    unittest.main(verbosity=2)
