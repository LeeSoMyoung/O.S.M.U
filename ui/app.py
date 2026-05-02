"""홈 화면 — 한눈에 보는 대시보드.

좌측 사이드바에서 다음 화면을 선택할 수 있다:
  1. 키워드 생성
  2. 키워드 풀 관리
  3. 추천 & 선택
  4. 설정
  5. 로그 / 상태
"""
from __future__ import annotations

import streamlit as st

from services import (
    get_pool_dataframe,
    get_content_dataframe,
    get_researcher,
    settings_snapshot,
)

st.set_page_config(
    page_title="O.S.M.U Keyword Researcher",
    page_icon="🌱",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 헤더 ─────────────────────────────────────────────────
st.title("🌱 O.S.M.U Keyword Researcher")
st.caption(
    "수익형 블로그 콘텐츠 자동화의 첫 단계 — "
    "씨앗 키워드를 입력하면 황금 키워드를 자동으로 찾아 정리해드려요."
)

# 첫 실행 안내
if "_seen_intro" not in st.session_state:
    st.info(
        "**처음 사용하시나요?** 좌측 메뉴에서 **‘① 키워드 생성’** 을 눌러 씨앗 키워드 한 단어로 시작해보세요."
    )
    st.session_state["_seen_intro"] = True

# ── 핵심 지표 카드 ───────────────────────────────────────
try:
    rs = get_researcher()
    pool = rs.storage.list_pool()
    content = rs.storage.list_content()
    settings = settings_snapshot()
except Exception as e:  # 초기 부팅 실패 — 친화적 안내
    st.error(f"초기 로딩 중 문제가 있었어요: {e}")
    st.stop()

c1, c2, c3, c4 = st.columns(4)
c1.metric("저장된 황금 키워드", f"{sum(1 for it in pool if it.status == 'golden')} 개")
c2.metric("전체 풀 크기", f"{len(pool)} 개", help=f"최대 {settings['POOL_MAX_SIZE']}개까지 보관")
c3.metric("작성한 글 수", f"{len(content)} 건")
c4.metric(
    "저장 위치",
    "구글 시트" if settings["storage_backend"] == "sheets" else "내 컴퓨터(CSV)",
    help="‘설정’ 화면에서 변경 가능합니다.",
)

st.divider()

# ── 빠른 시작 버튼 ───────────────────────────────────────
st.subheader("바로 시작하기")
b1, b2, b3 = st.columns(3)
with b1:
    if st.button("🌱  씨앗 키워드 입력하기", use_container_width=True, type="primary"):
        st.switch_page("pages/1_🌱_키워드_생성.py")
with b2:
    if st.button("⭐  추천 키워드 보기", use_container_width=True):
        st.switch_page("pages/3_⭐_추천_및_선택.py")
with b3:
    if st.button("📦  키워드 풀 관리", use_container_width=True):
        st.switch_page("pages/2_📦_키워드_풀.py")

# ── 미리보기: 추천 TOP 5 ─────────────────────────────────
st.subheader("⭐ 지금 추천드리는 키워드 TOP 5")
recs = rs.recommend(top_n=5)
if not recs:
    st.info(
        "아직 추천 가능한 키워드가 없어요. "
        "‘① 키워드 생성’ 에서 씨앗 키워드를 입력해 풀을 채워주세요."
    )
else:
    rec_rows = [
        {
            "순위": i + 1,
            "키워드": it.keyword,
            "점수": round(it.score, 1),
            "월 검색량": it.search_volume,
            "경쟁도": it.competition,
            "주제(seed)": it.seed_keyword,
        }
        for i, it in enumerate(recs)
    ]
    st.dataframe(rec_rows, use_container_width=True, hide_index=True)

st.divider()
st.caption(
    "💡 **사용 흐름** &nbsp; ① 키워드 생성 → ② 풀에서 확인 → ③ 추천된 키워드 선택 → "
    "**자동으로 ‘작성 대기’ 상태로 기록됩니다.**"
)
