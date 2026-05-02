"""세션 활동 로그.

st.session_state 에 최근 작업/에러를 기록 → 로그/상태 화면에서 보여준다.
파일 영속성은 옵션(향후 추가).
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

import streamlit as st

LOG_KEY = "_osmu_activity_log"
LEVELS = Literal["info", "success", "warning", "error"]


def _store() -> list[dict]:
    if LOG_KEY not in st.session_state:
        st.session_state[LOG_KEY] = []
    return st.session_state[LOG_KEY]


def log_activity(level: LEVELS, where: str, message: str, detail: str | None = None) -> None:
    _store().append(
        {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "level": level,
            "where": where,
            "message": message,
            "detail": detail or "",
        }
    )
    # 최근 200건만 유지
    if len(_store()) > 200:
        st.session_state[LOG_KEY] = _store()[-200:]


def get_activities() -> list[dict]:
    return list(reversed(_store()))  # 최신순


def clear_activities() -> None:
    st.session_state[LOG_KEY] = []
