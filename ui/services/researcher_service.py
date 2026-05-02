"""KeywordResearcher 싱글턴 + 설정 적용 헬퍼.

src/osmu_kr 패키지를 직접 import해서 사용한다(서브프로세스/HTTP 다리 X).
환경변수(Config)가 변경되면 reload_researcher()로 다시 만든다.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

# src 경로 등록 — 상위 폴더의 src/osmu_kr 를 import 가능하게 한다.
_HERE = Path(__file__).resolve().parent
_PROJECT_ROOT = _HERE.parent.parent
_SRC = _PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import streamlit as st  # noqa: E402  (sys.path 등록 이후)

from osmu_kr import Config, KeywordResearcher  # noqa: E402


# ─────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def _build_researcher() -> KeywordResearcher:
    return KeywordResearcher(Config())


def get_researcher() -> KeywordResearcher:
    return _build_researcher()


def reload_researcher() -> KeywordResearcher:
    """환경변수 변경 후 새 인스턴스 강제 생성."""
    _build_researcher.clear()
    return _build_researcher()


def settings_snapshot() -> dict[str, Any]:
    """현재 적용 중인 설정 요약 — 설정 화면과 상태 화면이 공통 사용."""
    cfg = get_researcher().cfg
    return {
        "storage_backend": cfg.resolved_backend(),
        "local_format": cfg.local_format,
        "local_xlsx_filename": cfg.local_xlsx_filename,
        "evaluator": cfg.evaluator,
        "POOL_MAX_SIZE": cfg.pool_max_size,
        "REVIVAL_DAYS": cfg.revival_days,
        "SEED_COOLDOWN_DAYS": cfg.seed_cooldown_days,
        "GOLDEN_THRESHOLD": cfg.golden_threshold,
        "MEDIUM_LOWER": cfg.medium_lower,
        "MEDIUM_UPPER": cfg.medium_upper,
        "sheet_id": cfg.sheet_id or "",
        "sheet_title": cfg.sheet_title,
        "credentials": cfg.google_credentials or "",
        "has_credentials": cfg.has_google_credentials,
        "data_dir": cfg.local_data_dir,
    }


def get_local_xlsx_path() -> str | None:
    """로컬 .xlsx 파일이 존재하면 절대 경로 반환 (다운로드 버튼용)."""
    import os
    cfg = get_researcher().cfg
    p = os.path.join(cfg.local_data_dir, cfg.local_xlsx_filename)
    return p if os.path.isfile(p) else None


def apply_settings(form_values: dict[str, Any]) -> None:
    """설정 화면 폼 → 환경변수 업데이트 → 인스턴스 재생성."""
    mapping = {
        "storage_backend": "OSMU_STORAGE_BACKEND",
        "local_format": "OSMU_LOCAL_FORMAT",
        "local_xlsx_filename": "OSMU_LOCAL_XLSX",
        "evaluator": "OSMU_EVALUATOR",
        "POOL_MAX_SIZE": "OSMU_POOL_MAX_SIZE",
        "REVIVAL_DAYS": "OSMU_REVIVAL_DAYS",
        "SEED_COOLDOWN_DAYS": "OSMU_SEED_COOLDOWN_DAYS",
        "GOLDEN_THRESHOLD": "OSMU_GOLDEN_THRESHOLD",
        "MEDIUM_LOWER": "OSMU_MEDIUM_LOWER",
        "MEDIUM_UPPER": "OSMU_MEDIUM_UPPER",
        "sheet_id": "OSMU_SHEET_ID",
        "sheet_title": "OSMU_SHEET_TITLE",
        "credentials": "GOOGLE_APPLICATION_CREDENTIALS",
        "data_dir": "OSMU_LOCAL_DATA_DIR",
    }
    for k, env_name in mapping.items():
        if k in form_values:
            v = form_values[k]
            if v is None or v == "":
                os.environ.pop(env_name, None)
            else:
                os.environ[env_name] = str(v)
    reload_researcher()


# ── 양방향 동기화 헬퍼 ──────────────────────────────────
def is_mirror_backend() -> bool:
    rs = get_researcher()
    return rs.storage.name == "mirror"


def sync_status() -> dict | None:
    """MirrorStorage 의 현재 동기화 상태 (mirror 백엔드일 때만)."""
    rs = get_researcher()
    if rs.storage.name != "mirror":
        return None
    return rs.storage.status().to_dict()


def pull_from_sheets() -> dict:
    """Google Sheets → 로컬 일괄 동기화."""
    rs = get_researcher()
    if rs.storage.name != "mirror":
        return {"ok": False, "reason": "이 백엔드는 동기화를 지원하지 않습니다."}
    return rs.storage.pull_from_sheets()


def push_to_sheets() -> dict:
    """로컬 → Google Sheets 일괄 업로드."""
    rs = get_researcher()
    if rs.storage.name != "mirror":
        return {"ok": False, "reason": "이 백엔드는 동기화를 지원하지 않습니다."}
    return rs.storage.push_to_sheets()


# ── DataFrame 변환 헬퍼 ──────────────────────────────────
def get_pool_dataframe():
    """keyword_pool 을 pandas DataFrame 으로 (정렬·필터에 사용).

    pandas 미설치 환경 대비: 단순 list[dict] 도 호환.
    """
    rs = get_researcher()
    items = rs.storage.list_pool()
    rows = []
    for it in items:
        rows.append(
            {
                "keyword_id": it.keyword_id,
                "seed_keyword": it.seed_keyword,
                "keyword": it.keyword,
                "score": it.score,
                "search_volume": it.search_volume,
                "competition": it.competition,
                "cpc": it.cpc,
                "commercial_intent": round(it.commercial_intent, 2),
                "status": it.status,
                "source": it.source,
                "updated_at": it.updated_at,
                "note": it.note,
            }
        )
    try:
        import pandas as pd

        return pd.DataFrame(rows)
    except ImportError:
        return rows


def get_content_dataframe():
    rs = get_researcher()
    rows = []
    for r in rs.storage.list_content():
        rows.append(
            {
                "id": r.id,
                "keyword": r.keyword,
                "seed_keyword": r.seed_keyword,
                "keyword_id": r.keyword_id,
                "status": r.status,
                "title_final": r.title_final,
                "created_at": r.created_at,
                "platform_url": r.platform_url,
            }
        )
    try:
        import pandas as pd

        return pd.DataFrame(rows)
    except ImportError:
        return rows
