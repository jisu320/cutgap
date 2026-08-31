"""네이버 플레이스 메뉴 목록에서 여성/남성 커트 가격만 골라낸다.

이 모듈이 프로젝트의 핵심이다. 네이버가 정렬에 쓰는 대표가격은
'앞머리컷' 같은 부분 시술이 뽑히는 경우가 많아서, 메뉴 전체를 보고
'진짜 커트'만 다시 판정한다.
"""

import re
import unicodedata

# 네이버가 메뉴에 직접 붙여주는 분류. 커트가 아닌 펌/염색/클리닉을 먼저 걷어낸다.
CUT_PRICE_TYPES = {"cut"}

# 커트로 오인되지만 우리가 원하는 '커트 한 번 값'이 아닌 것들.
EXCLUDE = (
    # 부분 시술
    "앞머리", "앞머", "뱅", "시스루", "옆머리", "뒷머리", "구렛나루", "구레나룻",
    "부분", "다듬", "정리", "숱", "층",
    # 나이·신분 할인가. 일반 커트값이 아니라서 최저가 정렬을 오염시킨다.
    # 노원구 실수집에서 최저가 상위가 전부 이쪽이었다.
    "학생", "초등", "중등", "고등", "초중고", "중고생", "고생", "청소년", "미성년",
    "유아", "아동", "어린이", "미취학", "베이비", "키즈",
    "세이상", "세이하", "경로", "노인", "어르신", "우대", "실버", "소인",
    "군인", "장병", "복지",
    # 커트가 아닌 시술
    "다운펌", "볼륨", "매직", "열펌", "세팅",
    "추가", "옵션", "상담", "삭발", "면도", "이발기", "바리깡",
    "가발", "붙임", "익스텐션", "반려", "애견",
)

FEMALE = ("여성", "여자", "우먼", "woman", "women", "레이디", "lady", "ladies", "girl", "걸")
# '이발'은 이용업의 남성 커트다. 중립으로 두면 여성가로도 잡혀서 값이 틀린다.
MALE = ("남성", "남자", "맨즈", "man", "men", "mens", "신사", "보이", "boy", "이발")

# '커트' 자체를 가리키는 표기들. priceType이 비어 있을 때의 대체 판정에 쓴다.
CUT_WORD = ("커트", "컷", "커팅", "cut", "이발")

# 네이버가 priceType='cut'으로 태깅했지만 커트가 아닌 시술.
# 이름에 커트 낱말이 전혀 없을 때만 제외한다('커트+드라이'는 살린다).
NOT_CUT = ("드라이", "스파", "샴푸", "스타일링", "트리트먼트", "케어", "왁싱")

_NUM = re.compile(r"(\d[\d,]*)")

# '컷(65세에서69세)' 처럼 나이 조건이 붙은 요금. 일반 커트값이 아니다.
_AGE = re.compile(r"\d+\s*세")

# 괄호로만 성별을 표기하는 메뉴명: '일반(여)', '커트[남]', '여/남 커트'.
# 괄호를 지운 뒤에는 구분할 수 없어서 지우기 전에 먼저 본다.
F_MARKS = ("(여)", "[여]", "/여", "-여", "여/", "(f)", "(w)")
M_MARKS = ("(남)", "[남]", "/남", "-남", "남/", "(m)")


def normalize(name):
    """비교용으로 메뉴명을 납작하게 만든다. 공백/기호 제거 + 소문자."""
    s = unicodedata.normalize("NFKC", name or "")
    s = s.lower()
    s = re.sub(r"[\s\-_/·,()\[\]{}+~!?.'\"]", "", s)
    return s


def light(name):
    """괄호는 남기고 공백만 지운 형태. 성별 괄호 표기를 보기 위한 것."""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", name or "").lower())


def parse_price(raw):
    """'36,000원' -> 36000. 숫자가 없으면 None('가격문의' 등)."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return int(raw)
    m = _NUM.search(str(raw))
    if not m:
        return None
    try:
        value = int(m.group(1).replace(",", ""))
    except ValueError:
        return None
    # 만원 단위 표기('3.6만' 같은 예외)나 오탐을 막는 최소한의 상식 범위.
    if value < 1000 or value > 2_000_000:
        return None
    return value


def is_cut_menu(menu):
    """이 메뉴가 '커트'인가. priceType을 우선 믿고, 없으면 이름으로 판단한다."""
    ptype = (menu.get("priceType") or "").lower()
    if ptype:
        return ptype in CUT_PRICE_TYPES
    flat = normalize(menu.get("name"))
    return any(w in flat for w in CUT_WORD)


def is_excluded(name):
    flat = normalize(name)
    if _AGE.search(flat):
        return True
    if any(bad in flat for bad in EXCLUDE):
        return True
    # 커트 낱말이 없는데 다른 시술명만 있으면 커트가 아니다
    if any(w in flat for w in NOT_CUT) and not any(w in flat for w in CUT_WORD):
        return True
    return False


def gender_of(name):
    """메뉴명에 성별 표기가 있으면 'w'/'m', 없으면 None.

    여성 표기를 먼저 찾아서 지운 뒤 남성 표기를 찾는다.
    'women'이 'men'을 품고 있어서 순서 없이 검사하면 둘 다 걸린다.
    """
    # 1순위: '여성' '맨즈' 같은 온전한 낱말. 괄호 표기보다 신뢰도가 높다.
    flat = normalize(name)
    hits_f = [k for k in FEMALE if k in flat]
    rest = flat
    for k in hits_f:
        rest = rest.replace(k, "")
    has_m = any(k in rest for k in MALE)
    if hits_f and has_m:
        return None          # '여성/남성 커트' 같은 공용 메뉴는 중립 취급
    if hits_f:
        return "w"
    if has_m:
        return "m"

    # 2순위: 낱말이 없을 때만 괄호 표기를 본다. '일반(여)' 같은 경우.
    marked = light(name)
    mark_f = any(k in marked for k in F_MARKS)
    mark_m = any(k in marked for k in M_MARKS)
    if mark_f and mark_m:
        return None
    if mark_f:
        return "w"
    if mark_m:
        return "m"
    return None


def _cheapest(candidates):
    """[(가격, 메뉴명)] 중 최저가 하나."""
    if not candidates:
        return None
    price, name = min(candidates, key=lambda c: c[0])
    return {"price": price, "src": name}


def extract_cut_prices(menus):
    """메뉴 배열 -> {'w': {...} | None, 'm': {...} | None, 'dropped': [...]}

    반환되는 각 항목:
      price : 원 단위 정수
      src   : 판정 근거가 된 원본 메뉴명 (UI에 그대로 노출한다)
      how   : 'exact'   성별이 명시된 메뉴에서 나옴
              'neutral' 성별 표기 없는 '커트' 메뉴를 양쪽에 공용으로 적용
    """
    female, male, neutral, dropped = [], [], [], []

    for menu in menus or []:
        name = menu.get("name") or ""
        price = parse_price(menu.get("price"))
        if not is_cut_menu(menu):
            continue
        if is_excluded(name):
            dropped.append(name)
            continue
        if price is None:
            dropped.append(name)
            continue
        bucket = gender_of(name)
        if bucket == "w":
            female.append((price, name))
        elif bucket == "m":
            male.append((price, name))
        else:
            neutral.append((price, name))

    result = {"w": None, "m": None, "dropped": dropped}

    for key, sexed in (("w", female), ("m", male)):
        picked = _cheapest(sexed)
        if picked:
            picked["how"] = "exact"
        else:
            picked = _cheapest(neutral)
            if picked:
                picked["how"] = "neutral"
        result[key] = picked

    return result
