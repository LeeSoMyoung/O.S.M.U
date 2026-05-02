# O.S.M.U Keyword Researcher — GUI (Streamlit)

> 비개발자를 위한 클릭 인터페이스. 기존 `osmu_kr` 패키지 코드는 **한 줄도 수정하지 않고** 위에 얹은 wrapper다.

---

## 한눈에 보는 폴더 구조

```
osmu_keyword_researcher/
├── src/osmu_kr/                ← 기존 본체 (이번 작업에서 수정 안 함)
├── ui/                         ← ★ 이번 작업으로 추가된 GUI
│   ├── app.py                      홈 대시보드
│   ├── pages/
│   │   ├── 1_🌱_키워드_생성.py
│   │   ├── 2_📦_키워드_풀.py
│   │   ├── 3_⭐_추천_및_선택.py
│   │   ├── 4_⚙️_설정.py
│   │   └── 5_📜_로그_상태.py
│   ├── services/
│   │   ├── researcher_service.py   KeywordResearcher 싱글턴 + DataFrame 변환
│   │   ├── error_translator.py     기술 에러 → 한국어 친화 메시지
│   │   └── activity_log.py         세션 작업 로그
│   ├── requirements.txt
│   ├── run_mac.command             Mac 더블클릭 실행
│   ├── run_windows.bat             Windows 더블클릭 실행
│   └── README.md
└── main.py                     ← `python main.py` 한 줄로 GUI 실행
```

---

## 실행 방법

### ✅ Mac

1. Finder에서 **`ui/run_mac.command`** 를 더블클릭.
   *(처음 한 번 “인증되지 않은 개발자”가 뜨면 우클릭 → 열기)*
2. 첫 실행에는 필요한 패키지가 자동 설치됩니다(1–2분).
3. 잠시 후 브라우저가 자동으로 열리면 사용 시작!

### ✅ Windows

1. 탐색기에서 **`ui/run_windows.bat`** 를 더블클릭.
2. 첫 실행에는 필요한 패키지가 자동 설치됩니다.
3. 브라우저에 페이지가 떠요.

### 또는 한 줄 명령

```bash
# 어떤 OS든 동일
pip install -r ui/requirements.txt
python main.py
```

---

## 화면 흐름 (3-클릭 사용 흐름)

```
   [홈 대시보드]
       │  ① 클릭 — “씨앗 키워드 입력하기”
       ▼
   [① 키워드 생성]  주제 입력 → ② 클릭 — “키워드 만들기”
       │
       ▼
   [③ 추천 & 선택]                      ← 사이드바 또는 홈에서 이동
       │  ③ 클릭 — “이 키워드로 글 쓰기”
       ▼
   ✅ 자동으로 ‘작성 대기’ 등록
```

총 **3-클릭 이내**에 키워드 자동 분석부터 콘텐츠 작성 대기까지 완료된다.

---

## 화면별 안내

### 🌱 ① 키워드 생성
- 주제(씨앗 키워드) 한 단어 입력 → ‘키워드 만들기’.
- 점수/검색량/경쟁도/CPC가 표로 정리되며, 점수에 따라 **⭐황금 / ✅좋음 / 🟡보통** 라벨.
- ‘🧪 이 키워드 강화하기’ — 보통 점수 키워드를 **롱테일 변형**으로 자동 재가공(키워드 연금술).

### 📦 ② 키워드 풀 관리
- 저장된 모든 키워드 한눈에 조회. 상태/주제/키워드 필터, 점수·검색량 정렬.
- 체크박스로 여러 행 선택 → **선택 삭제 / 선택 재평가**.
- 상단의 **🧹 지금 정리 실행** = `prune()` — 유효기간이 지난 키워드를 자동 재평가하거나 삭제.

### ⭐ ③ 추천 & 선택
- ‘재사용 간격(쿨다운)’이 적용된 결과만 보여줌 — 같은 주제로 짧은 간격에 다시 글 쓰는 일을 막아줌.
- ‘이 키워드로 글 쓰기’ → `select_for_content` 가 자동 실행되어 풀에서 빠지고 `content_db` 에 작성 대기로 등록.
- 쿨다운 위반 시: **“최근에 비슷한 주제의 글을 작성하셔서 잠시 사용할 수 없어요…”** 한국어 안내.

### ⚙️ ④ 설정
- 최대 보관 개수(`POOL_MAX_SIZE`), 재평가 주기(`REVIVAL_DAYS`), 동일 주제 재사용 간격(`SEED_COOLDOWN_DAYS`).
- 평가 방식: **기본(휴리스틱)** ↔ **네이버 검색광고 API**.
- 저장 위치: **내 컴퓨터(CSV)** ↔ **구글 시트** ↔ 자동.
- 저장 즉시 정책이 모듈에 반영(인스턴스 재생성).

### 📜 ⑤ 로그 / 상태
- 현재 백엔드/평가 방식/자격증명 유무 표시.
- 최근 작업 로그(성공/경고/에러) 시간순 누적.

---

## 기존 본체와 연결되는 방식

```
ui/services/researcher_service.py
    └── from osmu_kr import Config, KeywordResearcher       ← 직접 호출
                                            │
                                            ▼
                                   기존 src/osmu_kr 패키지 (수정 없음)
```

- `ui/` 는 **모든 기능을 wrapper 형태로** 호출한다. 서브프로세스나 HTTP 다리는 없다.
- 정책 변경은 환경변수를 갱신한 뒤 `KeywordResearcher` 를 재생성하는 방식으로 즉시 반영.
- 스토리지는 본체의 `BaseStorage` 를 그대로 재사용 — Sheets/Local 둘 다 자동 호환.

---

## 에러 메시지 정책 (요구사항 §7)

기술 용어를 사용자에게 노출하지 않는다. 예시:

| 내부 예외                         | UI 메시지                                                                 |
|-----------------------------------|---------------------------------------------------------------------------|
| `PermissionError(seed_cooldown…)` | 🛑 “최근에 비슷한 주제의 글을 작성하셔서 잠시 사용할 수 없어요…”          |
| `KeyError`                        | 🔍 “선택한 키워드를 더 이상 찾을 수 없어요. 새로고침을 눌러주세요.”       |
| `RuntimeError(gspread)`           | 🔧 “구글 시트 연동 패키지를 찾을 수 없어요…”                              |
| 그 외                             | ⚠️ “예상치 못한 문제가 발생했어요. ‘로그/상태’ 화면을 확인하세요.”         |

번역 규칙은 `ui/services/error_translator.py` 한 곳에서 관리.

---

## 배포 옵션 (.app / .exe)

`python main.py` 한 줄로 충분하지만, 더 친화적인 더블클릭 배포가 필요하면 PyInstaller로 패키징할 수 있다.

```bash
# Mac .app
pip install pyinstaller
pyinstaller --windowed --name "OSMU Keyword Researcher" \
    --add-data "ui:ui" --add-data "src:src" \
    --collect-all streamlit \
    main.py

# Windows .exe (Windows 환경에서 실행)
pyinstaller --noconsole --name "OSMU Keyword Researcher" ^
    --add-data "ui;ui" --add-data "src;src" ^
    --collect-all streamlit ^
    main.py
```

빌드된 결과물은 `dist/` 에 생성된다. 단일 .app/.exe로 배포할 수 있으며, 사용자는 Python을 따로 설치할 필요가 없다.

---

## 확장 방향 (요구사항 §10-5)

이 GUI는 “키워드 단계”를 책임진다. 다음 단계를 자연스럽게 이어 붙일 수 있다.

```
선택된 content_db 레코드 (status=대기중)
        │
        ▼
[다음 모듈]  OpenClaw로 기사 3개 크롤링 → raw_content 저장
        │
        ▼
[다음 모듈]  Unsplash 이미지 3장 + Claude 글 작성 → refined_post 저장
        │
        ▼
[다음 모듈]  Slack 검토 → PM 승인 → 티스토리 발행
```

각 단계는 별도의 Streamlit 페이지로 추가하거나, 동일한 데이터(`content_db`)를 바라보는 별도 모듈로 분리할 수 있다. 스토리지가 같은 인터페이스(`BaseStorage`)를 쓰기 때문에 어떤 단계든 즉시 연동 가능하다.

---

## 자주 묻는 질문

**Q. 인터넷 없이도 동작하나요?**
A. 네. 기본값은 ‘내 컴퓨터(CSV)’ 저장이라 오프라인에서도 모든 기능이 동작합니다. 구글 시트로 전환할 때만 인터넷이 필요해요.

**Q. 기존에 만든 데이터가 사라지나요?**
A. 본체와 동일한 `data/` 폴더(또는 같은 구글 시트)를 사용하므로 CLI로 만든 데이터를 GUI에서 그대로 이어 작업할 수 있습니다.

**Q. ‘발행’ 까지 자동화되나요?**
A. 현재 GUI는 키워드 단계까지 책임지고, 콘텐츠 생성·발행은 다음 단계 모듈에서 추가됩니다(확장 방향 참고).
