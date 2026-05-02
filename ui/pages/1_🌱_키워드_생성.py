"""① 키워드 생성 화면.

- seed 입력 박스
- ‘키워드 생성’ 버튼 → run_seed()
- 생성된 결과를 표(keyword/score/검색량/경쟁도/CPC/상태)로 보여준다
- ‘키워드 연금술 적용’ — 보통 점수 키워드를 long-tail 변형으로 강화

내부 용어(seed/pool/evaluator)는 사용자에게 노출하지 않는다.
"""
from __future__ import annotations

import streamlit as st

from services import (
    get_researcher,
    humanize_error,
    log_activity,
)
from osmu_kr.researcher.alchemist import transmute  # 연금술 직접 호출용

st.set_page_config(page_title="키워드 생성", page_icon="🌱", layout="wide")
st.title("🌱 ① 키워드 생성")
st.caption(
    "주제를 한 단어로 입력하면, 연관된 ‘좋은 키워드’ 후보를 자동으로 찾아 점수와 함께 보여드려요."
)

# ── 입력 폼 ─────────────────────────────────────────────
with st.form("seed_form"):
    seed = st.text_input(
        "어떤 주제로 글을 쓰고 싶으세요?",
        placeholder="예: 다이어트, AI ETF, 챗GPT 활용법",
        help="짧은 단어 또는 두세 단어 정도가 가장 잘 동작합니다.",
    )
    col_a, col_b = st.columns([1, 1])
    with col_a:
        limit = st.slider(
            "후보 키워드를 몇 개까지 만들까요?",
            min_value=5,
            max_value=20,
            value=10,
            help="값이 클수록 더 다양한 변형 키워드를 만들어요.",
        )
    with col_b:
        st.write("")  # spacer
        submit = st.form_submit_button(
            "✨  키워드 만들기",
            type="primary",
            use_container_width=True,
        )

# ── 실행 ────────────────────────────────────────────────
if submit:
    if not seed.strip():
        st.warning("주제를 한 단어 입력해주세요.")
    else:
        rs = get_researcher()
        try:
            with st.spinner("키워드를 만드는 중이에요…"):
                report = rs.run_seed(seed.strip(), expand_limit=limit)
            st.session_state["last_seed_report"] = report
            log_activity(
                "success",
                "키워드 생성",
                f"‘{seed}’로 키워드 {len(report.items)}개 만듦",
                report.summary(),
            )
            st.toast(f"키워드 {len(report.items)}개를 만들어 풀에 저장했어요 ✨", icon="✨")
        except Exception as e:  # 친화 메시지
            log_activity("error", "키워드 생성", humanize_error(e), str(e))
            st.error(humanize_error(e))

# ── 결과 표시 ───────────────────────────────────────────
report = st.session_state.get("last_seed_report")
if report and report.items:
    st.subheader(f"‘{report.seed}’ 에 대해 만든 키워드")

    # 요약 메트릭
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("후보 검토", f"{report.expanded} 개")
    m2.metric("✅ 풀에 저장", f"{report.accepted} 개")
    m3.metric("🧪 연금술 변형", f"{report.transmuted} 개")
    m4.metric("❌ 제외", f"{report.rejected} 개")

    rows = []
    for it in sorted(report.items, key=lambda x: x.score, reverse=True):
        # 상태 라벨을 친화적으로 변환
        status_label = (
            "⭐ 황금"
            if it.score >= 80
            else ("✅ 좋음" if it.score >= 65 else "🟡 보통")
        )
        rows.append(
            {
                "키워드": it.keyword,
                "점수": round(it.score, 1),
                "월 검색량": it.search_volume,
                "경쟁도": it.competition,
                "CPC(원)": it.cpc,
                "상태": status_label,
                "변형 여부": "🧪 변형" if "alchemy" in it.source else "—",
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)

    # ── 키워드 연금술 ───────────────────────────────────
    st.divider()
    st.subheader("🧪 키워드 연금술 — 따로 강화하고 싶은 키워드가 있나요?")
    st.caption(
        "원하는 키워드를 골라 ‘이 키워드 강화하기’를 누르면, 더 구체적이고 경쟁이 낮은 변형을 자동으로 만들어 평가합니다."
    )
    options = [it.keyword for it in report.items]
    target = st.selectbox(
        "강화할 키워드를 고르세요",
        options=options,
        index=0,
    )
    n_variants = st.number_input(
        "몇 개의 변형을 만들까요?", min_value=1, max_value=8, value=3, step=1
    )
    if st.button("🔬  이 키워드 강화하기"):
        rs = get_researcher()
        try:
            with st.spinner("변형을 만들고 평가하는 중…"):
                variants = transmute(target, max_variants=int(n_variants))
                added, results = [], []
                for v in variants:
                    if rs.storage.find_pool_by_keyword(v):
                        results.append((v, None, "이미 풀에 있어요"))
                        continue
                    item = rs.check_keyword(v, seed=target)
                    results.append((v, item.score, item.status))
                    if item.status == "golden":
                        added.append(v)
            if added:
                st.success(f"새로 풀에 추가된 변형: {len(added)}개 — {', '.join(added)}")
            else:
                st.info("점수가 충분히 높은 변형이 없었어요. 다른 키워드를 시도해보세요.")

            st.dataframe(
                [
                    {"변형 키워드": v, "점수": (round(s, 1) if s is not None else "-"), "결과": st_}
                    for v, s, st_ in results
                ],
                use_container_width=True,
                hide_index=True,
            )
            log_activity(
                "success",
                "키워드 연금술",
                f"‘{target}’ 변형 {len(variants)}개 평가, {len(added)}개 풀 추가",
            )
        except Exception as e:
            log_activity("error", "키워드 연금술", humanize_error(e), str(e))
            st.error(humanize_error(e))

else:
    st.info("아직 결과가 없어요. 위에서 주제를 입력하고 ‘키워드 만들기’를 눌러주세요.")
