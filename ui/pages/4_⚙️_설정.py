"""④ 설정 화면.

- 풀 정책 슬라이더(POOL_MAX_SIZE, REVIVAL_DAYS, SEED_COOLDOWN_DAYS)
- 평가 모듈 선택(휴리스틱 / 네이버 광고 API)
- 저장 위치(로컬 CSV / 구글 시트)
- 구글 시트 자격증명 경로 / 시트 ID 입력

‘저장’ 누르면 환경변수 갱신 + KeywordResearcher 재생성.
"""
from __future__ import annotations

import streamlit as st

from services import (
    apply_settings,
    humanize_error,
    log_activity,
    settings_snapshot,
)

st.set_page_config(page_title="설정", page_icon="⚙️", layout="wide")
st.title("⚙️ ④ 설정")
st.caption("정책 값과 저장 위치를 바꿀 수 있어요. 처음에는 기본값 그대로 사용해도 충분합니다.")

snap = settings_snapshot()

with st.form("settings_form"):
    st.subheader("정책")
    c1, c2, c3 = st.columns(3)
    with c1:
        pool_max_size = st.number_input(
            "최대 보관 개수",
            min_value=5,
            max_value=500,
            value=int(snap["POOL_MAX_SIZE"]),
            step=5,
            help="키워드 풀에 몇 개까지 보관할지 정합니다. 초과되면 점수 낮은 항목부터 정리돼요.",
        )
    with c2:
        revival_days = st.number_input(
            "재평가 주기(일)",
            min_value=0.1,
            max_value=90.0,
            value=float(snap["REVIVAL_DAYS"]),
            step=0.5,
            help="이 기간이 지난 키워드는 자동 재평가되거나 만료됩니다. 시연용은 0.1(=2.4시간)도 가능.",
        )
    with c3:
        seed_cooldown_days = st.number_input(
            "동일 주제 재사용 간격(일)",
            min_value=0.0,
            max_value=60.0,
            value=float(snap["SEED_COOLDOWN_DAYS"]),
            step=0.5,
            help="같은 주제로 글을 작성한 뒤 다음 글까지의 최소 간격. 중복 콘텐츠 방지용.",
        )

    st.subheader("점수 임계치")
    c4, c5, c6 = st.columns(3)
    with c4:
        golden_threshold = st.number_input(
            "‘황금’ 임계 점수", 0.0, 100.0, float(snap["GOLDEN_THRESHOLD"]), 1.0
        )
    with c5:
        medium_lower = st.number_input(
            "‘보통’ 하한", 0.0, 100.0, float(snap["MEDIUM_LOWER"]), 1.0,
            help="이 사이 점수는 자동으로 ‘키워드 연금술’ 변형 시도 대상이 됩니다.",
        )
    with c6:
        medium_upper = st.number_input(
            "‘보통’ 상한", 0.0, 100.0, float(snap["MEDIUM_UPPER"]), 1.0
        )

    st.subheader("평가 방식")
    evaluator = st.radio(
        "어떻게 점수를 매길까요?",
        options=["heuristic", "naver_ads"],
        index=0 if snap["evaluator"] == "heuristic" else 1,
        horizontal=True,
        format_func=lambda v: {
            "heuristic": "기본(휴리스틱) — 추가 가입 불필요",
            "naver_ads": "네이버 검색광고 API — API 키 필요",
        }[v],
    )

    st.subheader("저장 위치")
    backend_choice = st.radio(
        "어디에 저장할까요?",
        options=["local", "sheets", "mirror", "auto"],
        index=["local", "sheets", "mirror", "auto"].index(snap["storage_backend"])
        if snap["storage_backend"] in ("local", "sheets", "mirror", "auto")
        else 0,
        horizontal=True,
        format_func=lambda v: {
            "local": "💻 내 컴퓨터(CSV) — 가장 간단",
            "sheets": "☁️ 구글 시트만 — 팀 공유 우선",
            "mirror": "🔄 양방향 동기화(권장) — 컴퓨터+구글 시트 둘 다",
            "auto": "🤖 자동 — 자격증명 있으면 동기화, 없으면 내 컴퓨터",
        }[v],
    )
    if backend_choice == "mirror":
        st.info(
            "**양방향 동기화 모드** — 모든 변경은 내 컴퓨터에 즉시 저장되고, "
            "동시에 구글 시트에도 자동 미러링됩니다. 인터넷이 끊겨도 동작하며, "
            "시트에서 직접 수정한 내용은 ‘키워드 풀’ 화면의 **‘☁️ 시트에서 새로고침’** 버튼으로 가져올 수 있어요."
        )

    st.subheader("로컬 파일 형식")
    local_format = st.radio(
        "내 컴퓨터에 어떤 파일로 저장할까요?",
        options=["xlsx", "csv"],
        index=0 if snap.get("local_format", "xlsx") == "xlsx" else 1,
        horizontal=True,
        format_func=lambda v: {
            "xlsx": "📊 엑셀(.xlsx) — Excel/Numbers 에서 더블클릭으로 열림 (권장)",
            "csv": "📝 CSV — 가장 가볍고 텍스트 에디터로도 편집 가능",
        }[v],
    )
    local_xlsx_filename = st.text_input(
        "엑셀 파일 이름 (선택)",
        value=snap.get("local_xlsx_filename", "osmu_workbook.xlsx"),
        help="기본값으로 두면 ‘osmu_workbook.xlsx’ 가 생성됩니다.",
    )

    sheet_id = st.text_input(
        "구글 시트 ID (선택)",
        value=snap["sheet_id"],
        help="구글 시트 URL의 /d/ 다음 문자열. 비어 있으면 시트 제목으로 찾아요.",
    )
    sheet_title = st.text_input("구글 시트 제목 (선택)", value=snap["sheet_title"])
    credentials = st.text_input(
        "구글 서비스 계정 키 파일 경로 (선택)",
        value=snap["credentials"],
        help="예: /Users/me/credentials/service_account.json",
    )

    submit = st.form_submit_button("💾  저장하기", type="primary", use_container_width=True)

if submit:
    try:
        apply_settings(
            {
                "POOL_MAX_SIZE": pool_max_size,
                "REVIVAL_DAYS": revival_days,
                "SEED_COOLDOWN_DAYS": seed_cooldown_days,
                "GOLDEN_THRESHOLD": golden_threshold,
                "MEDIUM_LOWER": medium_lower,
                "MEDIUM_UPPER": medium_upper,
                "evaluator": evaluator,
                "storage_backend": backend_choice,
                "local_format": local_format,
                "local_xlsx_filename": local_xlsx_filename.strip() or "osmu_workbook.xlsx",
                "sheet_id": sheet_id.strip(),
                "sheet_title": sheet_title.strip(),
                "credentials": credentials.strip(),
            }
        )
        st.success("설정을 저장했어요. 새 정책이 즉시 적용됩니다.")
        log_activity("success", "설정", "설정 변경 적용")
    except Exception as e:
        log_activity("error", "설정", humanize_error(e), str(e))
        st.error(humanize_error(e))

# ── 현재 적용 상태 미리보기 ──────────────────────────────
st.divider()
st.subheader("현재 적용 중인 설정")
st.json(settings_snapshot())
