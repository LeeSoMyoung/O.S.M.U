"""스토리지 팩토리.

지원 backend:
  - local   : 로컬 단독 (CSV 또는 XLSX, OSMU_LOCAL_FORMAT으로 선택)
  - sheets  : Google Sheets 단독 (실시간)
  - mirror  : 로컬(엑셀/CSV) + Google Sheets 양방향 동기화 ★ 권장
  - auto    : 자격증명/시트 있으면 mirror, 없으면 local

OSMU_LOCAL_FORMAT (기본 'xlsx'):
  - xlsx : Excel/Numbers 에서 직접 열 수 있는 .xlsx 워크북 (시트 2개)
  - csv  : 단순 CSV 파일 두 개 (가장 가볍고 빠름)
"""
from __future__ import annotations

import logging

from ..config import Config
from .base import BaseStorage
from .csv_local import LocalCsvStorage

log = logging.getLogger(__name__)


def _build_local(cfg: Config) -> BaseStorage:
    """로컬 백엔드 — 사용자가 선택한 형식(csv/xlsx)에 맞춰 생성."""
    fmt = (cfg.local_format or "xlsx").lower()
    if fmt == "xlsx":
        try:
            from .xlsx_local import LocalXlsxStorage  # noqa: WPS433

            return LocalXlsxStorage(
                data_dir=cfg.local_data_dir,
                filename=cfg.local_xlsx_filename,
            )
        except ImportError as e:
            log.warning("[factory] openpyxl 미설치 → CSV 폴백: %s", e)
    return LocalCsvStorage(data_dir=cfg.local_data_dir)


def _try_build_sheets(cfg: Config):
    """SheetsStorage 인스턴스 생성 시도. 실패하면 None."""
    try:
        from .sheets import SheetsStorage  # noqa: WPS433

        if not cfg.google_credentials:
            log.info("[factory] GOOGLE_APPLICATION_CREDENTIALS 없음")
            return None
        return SheetsStorage(
            credentials_path=cfg.google_credentials,
            sheet_id=cfg.sheet_id,
            sheet_title=cfg.sheet_title,
            ws_keyword_pool=cfg.ws_keyword_pool,
            ws_content_db=cfg.ws_content_db,
        )
    except Exception as e:
        log.warning("[factory] Sheets 초기화 실패: %s", e)
        return None


def build_storage(cfg: Config) -> BaseStorage:
    backend = cfg.resolved_backend()

    # ── auto: 자격증명/시트가 있으면 mirror, 없으면 local ──
    if backend == "auto":
        backend = "mirror" if (cfg.has_google_credentials and cfg.sheet_id) else "local"
        log.info("[factory] auto → %s", backend)

    # ── 단독 sheets ──────────────────────────────────
    if backend == "sheets":
        sh = _try_build_sheets(cfg)
        if sh is not None:
            return sh
        log.warning("[factory] sheets 실패 → 로컬 폴백")
        return _build_local(cfg)

    # ── mirror: local(엑셀/CSV) + sheets 양방향 ──
    if backend == "mirror":
        from .mirror import MirrorStorage  # 지연 import

        local = _build_local(cfg)

        def _factory():
            sh = _try_build_sheets(cfg)
            if sh is None:
                raise RuntimeError(
                    "Sheets 자격증명/시트 정보가 없거나 잘못됐습니다. "
                    "설정 화면에서 GOOGLE_APPLICATION_CREDENTIALS와 OSMU_SHEET_ID를 확인하세요."
                )
            return sh

        return MirrorStorage(local=local, sheets_factory=_factory)

    # ── 기본: local ──
    return _build_local(cfg)
