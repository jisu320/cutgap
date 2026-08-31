# 컷값 (cutgap)

미용실 **커트 가격**만 골라서 최저가순으로 보여주는 정적 사이트.

네이버 지도에서 미용실을 가격순으로 정렬하면 대표가격이 잡히는데, 그게 자주
`앞머리컷`이다. 실제로 확인한 가게 하나는 대표가격이 `앞머리컷 10,000원`,
진짜 커트는 `커트 36,000원`이었다. 그래서 정렬이 쓸모없어진다.

이 프로젝트는 메뉴판 전체를 보고 **커트로 분류된 항목만** 남긴 뒤
앞머리·부분컷·학생컷 등을 제외하고 **여성/남성 커트 최저가**를 뽑는다.

## 어떻게 동작하나

```
[1단계] 목록 수집   pcmap 목록 API  →  업소 id·이름·주소·좌표  (요청 1회에 수십 곳, 싸다)
[2단계] 가격 갱신   업소별 가격 페이지 → 메뉴 전체 → 커트만 판정  (업소당 1회, 비싸다)
[3단계] 정적 배포   docs/data/*.json  →  GitHub Pages
```

2단계가 병목이라 **하루 예산만큼 가장 오래 확인 안 된 곳부터** 돌린다.
예산을 전체 업소 수 ÷ 60으로 두면 두 달에 한 바퀴가 돈다.

핵심 판정 로직은 [`cutprice/menu.py`](cutprice/menu.py) 하나에 모여 있고
[`tests/test_menu.py`](tests/test_menu.py)가 실측 데이터로 검증한다.

## 처음 세팅

### 1. 지도 키

네이버 클라우드 플랫폼 → Maps → Application 등록 → **Web Dynamic Map** 활성화 →
Key ID를 `docs/config.js`의 `mapKeyId`에 넣는다. 허용 도메인에
`https://jisu320.github.io` 를 추가해야 한다.

지도 표시용 **공식 API**라 이 부분은 약관상 문제가 없다.
키는 도메인 제한이 걸린 공개 클라이언트 키라 저장소에 그대로 둬도 된다.

### 2. GitHub 저장소

```bash
# 저장소를 먼저 github.com/jisu320 에 cutgap 이름으로 만든 다음
git remote add origin git@github.com:jisu320/cutgap.git
git push -u origin main
```

Settings → Pages → Source `Deploy from a branch`, Branch `main`, Folder `/docs`.
Settings → Actions → General → Workflow permissions → **Read and write** 로 둔다.

### 3. 데이터 채우기

```bash
pip install -r requirements.txt

# 지역 트리 정찰 (시도 17개만 훑어서 시군구를 알아낸다)
python -m cutprice.enumerate_places --level sido --budget 60

# 시군구 단위 수집. 여기서 동 이름까지 배운다
python -m cutprice.enumerate_places --level sigungu --budget 1200

# 동 단위 전수 수집. 여러 번 나눠 돌린다
python -m cutprice.enumerate_places --level dong --budget 1500

# 가격 갱신 (매일 Actions가 자동으로 돈다)
python -m cutprice.refresh_prices --budget 2000
```

수집 전에 화면만 보려면 예시 데이터를 쓴다.

```bash
python -m cutprice.make_sample
cd docs && python -m http.server 8000
python -m cutprice.make_sample --clear   # 실제 수집 시작할 때 지운다
```

### 4. Actions 변수 (Settings → Variables)

| 이름 | 기본값 | 뜻 |
|---|---|---|
| `DAILY_BUDGET` | 2000 | 하루 최대 요청 수 |
| `REQUEST_DELAY` | 3.0 | 요청 간 최소 간격(초) |

전국 업소 수를 확인한 다음 `DAILY_BUDGET = 전체 ÷ 60` 으로 맞춰라.

## 수집 예의

네이버 약관은 자동 수집을 허용하지 않는다. 느리게 긁는 것이 허용으로 바뀌지는
않는다. 그래서 부하와 노출을 줄이는 쪽으로만 설계했고, 다음을 지킨다.

- 요청 간격 3초 + 지터, 429를 받으면 60초부터 지수적으로 물러난다
  (실측에서 짧은 버스트에도 바로 429가 떨어졌다)
- 하루 요청 예산을 넘기면 스스로 멈춘다
- 원문 HTML을 저장하지 않는다. **커트로 분류된 메뉴의 이름·가격만** 남긴다
  (펌·염색·클리닉 등은 저장하지 않는다). 판정 규칙을 고칠 때 재수집하지
  않으려면 이 정도는 남겨야 한다 — `python -m cutprice.reparse`
- 모든 항목에 네이버 원본 링크를 건다
- 중단 요청이 오면 즉시 워크플로를 끄고 데이터를 내린다

업소 목록의 공식 출처로 [지방행정 인허가데이터](https://www.localdata.go.kr)를
쓰는 것도 가능하다(미용업 전수 + 좌표 제공). 지금은 좌표까지 목록 API에서
같이 오기 때문에 쓰지 않는다.

## 전제 검증

`python -m cutprice.audit` 은 수집한 데이터로 **네이버 대표가격과 우리가 판정한
커트 가격이 얼마나 어긋나는지** 세어준다. '가격순 정렬이 앞머리컷 값으로 된다'는
문제의 실제 빈도를 네 데이터로 확인하는 용도다.

2026-08-31에 마포 지역 58곳을 표본으로 봤을 때는 대표가격 메뉴명이 55곳 모두
`컷`이었고 `앞머리컷`으로 잡힌 곳은 없었다. 표본이 한 지역 58곳뿐이니 결론은
아니지만, 문제의 원인이 목록 카드의 대표가격이 아니라 **지도 UI의 가격 필터·정렬
기준**일 가능성이 있다. `audit`으로 전국 데이터를 모은 뒤 다시 판단해라.

그 결과와 무관하게 이 도구가 주는 것은 두 가지다.

- **성별 구분**: 네이버 대표가격은 하나뿐이라 여성/남성 커트를 나눠주지 않는다
- **근거 공개**: 어떤 메뉴를 커트로 판정했는지 원문 메뉴명을 그대로 보여준다

## 한계

- **비공식 엔드포인트**라 네이버가 응답 구조를 바꾸면 깨진다. 접근 코드는
  [`cutprice/naver.py`](cutprice/naver.py) 하나에 격리해 뒀다.
- 목록 API의 `page` 파라미터 동작은 아직 확인 못 했다(확인 도중 429). 코드는
  2페이지가 새 결과를 안 주면 페이지네이션이 없다고 판단하고 지역을 더 쪼개는
  쪽으로 자동 전환한다.
- 메뉴명이 제각각이라 오분류가 난다. 그래서 판정 근거 메뉴명을 화면에 그대로
  노출하고 오분류 신고를 받는다. 규칙은 `cutprice/menu.py`의 `EXCLUDE`,
  `FEMALE`, `MALE` 세 목록만 고치면 된다.
- 성별 표기가 없는 `커트` 단일 메뉴는 남녀 공용으로 간주하고 화면에
  `성별 구분 없음`으로 표시한다.

## 테스트

```bash
python -m unittest discover -s tests -v
```

## 파일 배치

| 경로 | 역할 |
|---|---|
| `cutprice/menu.py` | 커트 판정 규칙. 오분류는 여기만 고친다 |
| `cutprice/naver.py` | 비공식 엔드포인트 접근. 네이버가 바뀌면 여기만 고친다 |
| `cutprice/enumerate_places.py` | 1단계 목록 수집 |
| `cutprice/refresh_prices.py` | 2단계 가격 갱신(순환) |
| `cutprice/regions.py` | 지역 트리 자가 학습 |
| `cutprice/reparse.py` | 저장된 메뉴로 재판정. 규칙 수정 후 네트워크 없이 반영 |
| `cutprice/audit.py` | 대표가격 대비 어긋남 통계 |
| `docs/` | GitHub Pages 정적 사이트 |
