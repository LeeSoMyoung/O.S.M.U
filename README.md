# O.S.M.U Keyword Researcher

> O.S.M.U (One Source Multi Use) 콘텐츠 자동화 파이프라인의 **상위 입력 모듈**.
> seed 키워드 → 황금 키워드 후보 → keyword_pool 자동 적재 → 추천 → content_db 까지의 **라이프사이클 전체**를 책임진다.
>
> 본 모듈은 description 의 완성 기준 3축을 모두 충족하도록 설계되었다.
> 1. Codespace 환경에서 즉시 실행 가능 (gspread 미설치 / 자격증명 미보유 상태에서도 로컬 폴백으로 동작)
> 2. **seed 단위 사용 이력 기반 간격 제어** (동일 seed 의 짧은 간격 반복 생성 차단)
> 3. **keyword_pool 의 라이프사이클 4단계** (CREATE / UPDATE-연금술 / DELETE-만료 / RECOMMEND) 자동화

---

## 아키텍처

```
                         ┌──────────────────────────────────────────────────┐
                         │                  KeywordResearcher                │
                         │           (osmu_kr.researcher.researcher)         │
                         └───────────────────┬───────────────────┬──────────┘
                                             │                   │
                       ┌─────────────────────┴───┐   ┌───────────┴────────────┐
                       │   evaluator (DI)        │   │   storage (DI)         │
                       │  ┌────────────────────┐ │   │  ┌──────────────────┐  │
                       │  │ HeuristicEvaluator │ │   │  │ SheetsStorage    │  │
                       │  └────────────────────┘ │   │  │  (gspread)       │  │
                       │  ┌────────────────────┐ │   │  └──────────────────┘  │
                       │  │ NaverAdsEvaluator  │ │   │  ┌──────────────────┐  │
                       │  │  (stub→실API 교체) │ │   │  │ LocalCsvStorage  │  │
                       │  └────────────────────┘ │   │  │  (폴백)          │  │
                       └─────────────────────────┘   │  └──────────────────┘  │
                                                     └────────────────────────┘
```

### 핵심 의사결정

| 결정          | 채택안                                     | 이유                                                         |
|---------------|--------------------------------------------|--------------------------------------------------------------|
| 데이터 모델   | **정규화 + content_db 사용이력 추적**     | description 권고. 멀티 계정 확장성 확보.                     |
| Sheets 연동   | **실연동 + 로컬 CSV 폴백**                | 자격증명 없을 때도 Codespace 즉시 데모, 동일 인터페이스 유지.|
| 평가 모듈     | **휴리스틱 + 외부 API 인터페이스 stub**   | "평가 함수 입출력 명확 / API 전환 시 인터페이스 유지" 충족.  |

`keyword_pool` 의 `last_used_at` 필드는 두지 않는다. 사용 이력은 `content_db.created_at` 으로
조회한다 (description 의 단일계정 종속성 우려 해결).

---

## 빠른 시작

### Codespace / 로컬

```bash
git clone <repo>
cd osmu_keyword_researcher

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

# 시연 시나리오 ① — seed → 후보 → 평가 → pool 저장 (+ 키워드 연금술)
PYTHONPATH=src python demos/scenario_1.py

# 시연 시나리오 ② — POOL_MAX_SIZE=5 / REVIVAL_DAYS=0.1 정책 검증
PYTHONPATH=src python demos/scenario_2.py

# 단위 테스트
PYTHONPATH=src python tests/test_basic.py
```

자격증명이 없으면 자동으로 `./data/*.csv` 로컬 폴백으로 동작한다. 실연동을 원하면
`.env` 파일 (또는 환경변수)에 `GOOGLE_APPLICATION_CREDENTIALS` 와 `OSMU_SHEET_ID` 를
설정하면 된다 (`.env.example` 참고).

### CLI

```bash
osmu-kr seed --seed "다이어트"
osmu-kr check --keyword "AI ETF 추천 2025"
osmu-kr recommend --top 5
osmu-kr select --id 0001 --title "직장인 다이어트 식단 7일 챌린지"
osmu-kr prune
osmu-kr show
```

---

## 라이프사이클 매핑 (description ↔ 코드)

| 단계                            | description 정의                                                | 구현 위치                                           |
|---------------------------------|------------------------------------------------------------------|-----------------------------------------------------|
| ① CREATE — seed 입력            | seed → 관련 키워드 5~10개 → 평가 → pool 저장                    | `KeywordResearcher.run_seed()` + `expander.expand()` |
| ② UPDATE — 키워드 연금술        | medium 키워드를 변형해 황금으로 재가공                          | `researcher.alchemist.transmute()` (run_seed/prune 내부에서 자동) |
| ③ CHECK + CREATE — 직접 입력    | 사용자가 직접 입력한 키워드 평가 후 pool 반영                   | `KeywordResearcher.check_keyword()`                 |
| ④ DELETE / UPDATE — 풀 관리     | POOL_MAX_SIZE 초과 / REVIVAL_DAYS 초과 시 정리                  | `researcher.manager.prune()`                        |
| ⑤ RECOMMEND — 추천              | seed cooldown + 연속 주제 회피 후 score 상위 추천                | `researcher.recommender.recommend()`                |
| ⑥ SELECT — 사용 처리            | 추천 키워드 선택 → pool 제거 + content_db 기록                  | `KeywordResearcher.select_for_content()`            |

### seed 간격 제어 (description 의 두 번째 완성 기준)

- 모든 콘텐츠 작성은 `select_for_content()` 를 거친다.
- 이 함수는 `content_db` 를 조회해 동일 `seed_keyword` 가 `OSMU_SEED_COOLDOWN_DAYS` 일 내에
  사용된 적이 있으면 `PermissionError` 로 차단한다.
- `recommend()` 도 같은 기준을 적용해 후보 자체에서 제외한다.
- 마지막으로 작성된 콘텐츠와 동일한 seed 는 (cooldown 무관) 추천에서도 제외해
  "연속 주제 회피" 요구사항을 충족한다.

```python
# 예시
rs.select_for_content(pick.keyword_id)
# 잠시 후, 같은 seed 의 다른 키워드 선택 시도
rs.select_for_content(other.keyword_id)
# → PermissionError: seed_cooldown 위반: '다이어트' 는 최근 7일 내에 사용됨
```

---

## 데이터 스키마

### keyword_pool (신규 시트)

| 컬럼                | 타입       | 설명                                       |
|---------------------|------------|--------------------------------------------|
| keyword_id          | string PK  | 0001 부터 자동 부여                        |
| seed_keyword        | string     | 발원 seed (간격 제어의 기준)               |
| keyword             | string     | 실제 황금 키워드 또는 연금술 변형형        |
| search_volume       | int        | 월 검색량                                  |
| competition         | enum       | 낮음 / 중간 / 높음                        |
| cpc                 | number     | 클릭당 광고 단가 (KRW)                     |
| commercial_intent   | float      | 0~1, 추천/비교/리뷰 등 키워드 가중치       |
| score               | float      | 0~100 황금 점수                            |
| status              | enum       | golden / medium / rejected / used / expired|
| created_at          | iso8601    | 풀 적재 시점                               |
| updated_at          | iso8601    | 마지막 재평가 시점 (REVIVAL 기준)          |
| source              | string     | heuristic / heuristic+alchemy / naver_ads  |
| note                | string     | 메모 (예: `transmuted from '다이어트'`)    |

### content_db (기획서 §1 와 호환 + 확장 컬럼)

기존 헤더 (`id`, `keyword`, `original_source`, `status`, `title_final`, `platform_url`,
`created_at`, `published_at`, `raw_content`, `refined_post`, `image_urls`, `error_log`,
`note`) 에 두 컬럼이 추가된다.

| 신규 컬럼      | 설명                                                   |
|----------------|--------------------------------------------------------|
| seed_keyword   | seed 단위 간격 제어를 위해 비정규화 저장               |
| keyword_id     | keyword_pool 의 외래키. 추후 join 가능                 |

---

## 환경변수

`.env.example` 참고. 핵심:

| 변수                      | 기본값        | 의미                                         |
|---------------------------|---------------|----------------------------------------------|
| `OSMU_STORAGE_BACKEND`    | `auto`        | `auto` / `sheets` / `local`                  |
| `OSMU_EVALUATOR`          | `heuristic`   | `heuristic` / `naver_ads`                    |
| `OSMU_POOL_MAX_SIZE`      | `50`          | 풀 최대 크기                                 |
| `OSMU_REVIVAL_DAYS`       | `14`          | 재평가/만료 임계 (일)                        |
| `OSMU_SEED_COOLDOWN_DAYS` | `7`           | 동일 seed 재사용 최소 간격 (일)              |
| `OSMU_GOLDEN_THRESHOLD`   | `70`          | 황금 점수 임계                               |
| `OSMU_MEDIUM_LOWER`       | `40`          | medium 하한 (연금술 적용 범위)               |
| `OSMU_MEDIUM_UPPER`       | `70`          | medium 상한                                  |

---

## 시연 결과 요약

### 시나리오 ① (seed → pool, 연금술)

3개 seed (`다이어트`, `AI ETF`, `챗GPT 활용법`) 입력 시 27개의 황금 키워드 후보가 자동
적재되며, 그 중 7~8개는 키워드 연금술이 만들어낸 long-tail 변형 (`직장인 + seed + 의도어`)이
가장 높은 점수를 받았다. 자세한 로그는 `demo_scenario_1.log` 참고.

### 시나리오 ② (POOL_MAX_SIZE=5, REVIVAL_DAYS=0.1)

- POOL_MAX_SIZE=5 가 자동 적용되어 27개 → **5개로 정리**
- 모든 항목의 `updated_at` 을 0.2일 과거로 만든 뒤 `prune()` 호출 → **5건 모두 자동 재평가**
- 의도적으로 추가한 medium 키워드 (#9999) 는 `prune()` 후 **풀에서 제거됨**
- 동일 seed (`AI ETF`) 콘텐츠 작성 직후 같은 seed 재사용 시도 → **`PermissionError` 로 차단**
- `recommend()` 결과에서도 차단된 seed 가 후보에서 제외됨

```
[1] 두 seed 실행 → 풀이 자동으로 POOL_MAX_SIZE=5로 정리되는지 확인
   ▶ 현재 pool 크기 = 5 (기대: ≤5)

[2] 모든 풀 항목의 updated_at을 0.2일 과거로 만든 뒤 prune() 호출
   ▶ prune 결과: revaluated=5 refreshed=5 expired=0 transmuted=0 overflow_removed=0

[2-b] 의도적으로 점수가 낮은 키워드를 풀에 끼워 넣고 prune → 삭제(expire) 확인
   ▶ '9999' 만료 처리 결과: EXPIRED ✅

[3] 동일 seed 기반 콘텐츠 간격 제어 검증
    ✅ 차단됨 (예상대로): seed_cooldown 위반: 'AI ETF' 는 최근 0.1일 내에 사용됨
     - 추천 후보 seed: ['다이어트', '챗GPT 활용법']  (AI ETF 제외 OK)
```

전체 출력은 `demo_scenario_2.log` 참고.

---

## 평가 모듈 교체 (Naver Ads API 등)

`osmu_kr.evaluator.base.BaseEvaluator` 를 상속해 `evaluate(keyword: str, *, seed: str)
-> Evaluation` 한 메서드만 구현하면 된다.

```python
from osmu_kr.evaluator.base import BaseEvaluator
from osmu_kr.models import Evaluation

class MyCustomEvaluator(BaseEvaluator):
    name = "my_custom"
    def evaluate(self, keyword, *, seed=""):
        # 외부 API 호출 ...
        return Evaluation(search_volume=..., competition=..., cpc=..., score=...)

researcher = KeywordResearcher(evaluator=MyCustomEvaluator())
```

`OSMU_EVALUATOR=naver_ads` 로 환경변수를 변경하면 `NaverAdsEvaluator` 가 로드되고,
자격증명이 채워져 있으면 (현재는 stub 단계) 휴리스틱과 100% 동일한 인터페이스로 응답한다.

---

## 통합 단계 (다음 작업)

본 모듈은 description 마지막 단락의 결론대로 콘텐츠 생성 파이프라인의 **상위 입력**이다.
다음 통합 흐름이 가능해진다.

```
KeywordResearcher.recommend()
        │ (PM 선택)
        ▼
KeywordResearcher.select_for_content()  ← content_db 레코드 생성 (status=대기중)
        │
        ▼
[기존 OSMU 파이프라인 — OpenClaw 크롤링 → Unsplash → Claude 글 생성 → Slack 검토 → 티스토리 발행]
```

`select_for_content()` 가 만든 레코드는 기획서 §1 의 헤더와 그대로 호환되므로
이미 작성한 워크플로 코드를 변경하지 않고 이어붙일 수 있다.

---

## 라이센스 / 작성

O.S.M.U 프로젝트 내부 사용. PM/엔지니어링 합작.
