"""MirrorStorage — Local CSV ↔ Google Sheets 양방향 동기화.

설계 원칙
─────────────────────────────────────────────────────────
1. **Local-first read**: 모든 읽기는 로컬 캐시에서 → 빠른 UI 응답.
2. **Dual write**: 모든 쓰기(upsert/delete/replace)는 로컬과 Sheets 둘 다에.
                   Sheets 호출이 실패해도 로컬은 갱신되며, 실패 사실은 메타에 기록.
3. **Explicit pull**: `pull_from_sheets()` 로 Sheets → 로컬 일괄 갱신.
                   사용자가 Sheets를 직접 수정한 경우 이 함수로 끌어온다.
4. **Explicit push**: `push_to_sheets()` 로 로컬 → Sheets 일괄 업로드.
                   인터넷 끊긴 동안 쌓인 변경을 한 번에 올릴 때 사용.
5. **충돌 정책**: 항상 마지막 쓰는 쪽이 이긴다 (last-write-wins).
                  멀티 계정/동시편집은 v0.1 범위 밖.

이 백엔드는 자격증명/시트가 없으면 우아하게 LocalCsvStorage 와 동일하게 동작한다.
즉 "Sheets 안 가능 → 로컬만" 자동 폴백.

기존 osmu_kr 코어 코드는 일절 수정하지 않는다 — BaseStorage 인터페이스를 그대로 구현한다.
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from ..models import ContentRecord, KeywordPoolItem
from .base import BaseStorage
from .csv_local import LocalCsvStorage  # noqa: F401  (메타 경로 호환용)

log = logging.getLogger(__name__)


@dataclass
class SyncStatus:
    sheets_enabled: bool
    last_pull_at: Optional[str] = None
    last_push_at: Optional[str] = None
    last_error: Optional[str] = None
    pending_writes: int = 0  # Sheets 쓰기에 실패해 보류 중인 변경 수
    sheet_url: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "sheets_enabled": self.sheets_enabled,
            "last_pull_at": self.last_pull_at,
            "last_push_at": self.last_push_at,
            "last_error": self.last_error,
            "pending_writes": self.pending_writes,
            "sheet_url": self.sheet_url,
        }


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S%z")


class MirrorStorage(BaseStorage):
    """LocalCsvStorage + SheetsStorage 미러링 래퍼."""

    name = "mirror"

    def __init__(
        self,
        local: BaseStorage,            # LocalCsvStorage / LocalXlsxStorage 모두 가능
        sheets_factory=None,            # callable -> SheetsStorage | None
        meta_path: Optional[str] = None,
    ):
        self.local = local
        self._sheets_factory = sheets_factory
        self._sheets: Optional[BaseStorage] = None  # 지연 로딩
        self._sheets_init_attempted = False

        # 메타 파일 경로는 local.data_dir 가 있는 경우 그 옆에, 아니면 ./data 에
        data_dir = getattr(local, "data_dir", "./data")
        self.meta_path = meta_path or os.path.join(data_dir, "_sync_meta.json")
        self._status = self._load_status()

    # ── 상태 / 메타 ──────────────────────────────────────
    def _load_status(self) -> SyncStatus:
        if os.path.isfile(self.meta_path):
            try:
                with open(self.meta_path, "r", encoding="utf-8") as f:
                    d = json.load(f)
                return SyncStatus(**{**SyncStatus(False).to_dict(), **d})
            except Exception:
                pass
        return SyncStatus(sheets_enabled=False)

    def _save_status(self) -> None:
        try:
            with open(self.meta_path, "w", encoding="utf-8") as f:
                json.dump(self._status.to_dict(), f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def status(self) -> SyncStatus:
        return self._status

    # ── Sheets 지연 초기화 ──────────────────────────────
    def _get_sheets(self) -> Optional[BaseStorage]:
        if self._sheets is not None:
            return self._sheets
        if self._sheets_init_attempted:
            return None
        self._sheets_init_attempted = True
        if not self._sheets_factory:
            self._status.sheets_enabled = False
            return None
        try:
            self._sheets = self._sheets_factory()
            self._status.sheets_enabled = True
            # SheetsStorage 가 sheet URL 을 노출하면 함께 저장
            sh = getattr(self._sheets, "_sh", None)
            if sh is not None:
                url = getattr(sh, "url", None)
                if url:
                    self._status.sheet_url = url
            self._save_status()
            log.info("[mirror] Sheets 백엔드 활성화 (%s)", self._status.sheet_url)
        except Exception as e:
            self._status.sheets_enabled = False
            self._status.last_error = f"sheets init failed: {e}"
            self._save_status()
            log.warning("[mirror] Sheets 초기화 실패 → 로컬 단독 동작: %s", e)
        return self._sheets

    # ── 쓰기 미러링 ───────────────────────────────────
    def _safe_sheets_call(self, fn_name: str, *args, **kwargs) -> bool:
        sh = self._get_sheets()
        if sh is None:
            self._status.pending_writes += 1
            self._save_status()
            return False
        try:
            getattr(sh, fn_name)(*args, **kwargs)
            self._status.last_push_at = _now()
            self._status.last_error = None
            self._save_status()
            return True
        except Exception as e:
            self._status.last_error = f"{fn_name} 실패: {e}"
            self._status.pending_writes += 1
            self._save_status()
            log.warning("[mirror] sheets.%s 실패: %s", fn_name, e)
            return False

    # ── BaseStorage: keyword_pool ──────────────────────
    def list_pool(self) -> List[KeywordPoolItem]:
        return self.local.list_pool()

    def get_pool(self, keyword_id: str) -> Optional[KeywordPoolItem]:
        return self.local.get_pool(keyword_id)

    def upsert_pool(self, item: KeywordPoolItem) -> None:
        self.local.upsert_pool(item)
        self._safe_sheets_call("upsert_pool", item)

    def delete_pool(self, keyword_id: str) -> bool:
        ok = self.local.delete_pool(keyword_id)
        self._safe_sheets_call("delete_pool", keyword_id)
        return ok

    def replace_pool(self, items: List[KeywordPoolItem]) -> None:
        self.local.replace_pool(items)
        self._safe_sheets_call("replace_pool", items)

    # ── BaseStorage: content_db ────────────────────────
    def list_content(self) -> List[ContentRecord]:
        return self.local.list_content()

    def append_content(self, record: ContentRecord) -> None:
        self.local.append_content(record)
        self._safe_sheets_call("append_content", record)

    # ── 명시적 동기화 API ─────────────────────────────
    def pull_from_sheets(self) -> dict:
        """Sheets → Local 일괄 동기화. 사용자가 Sheets에서 직접 수정한 변경을 끌어온다."""
        sh = self._get_sheets()
        if sh is None:
            return {"ok": False, "reason": "sheets_unavailable"}

        try:
            t0 = time.time()
            pool = sh.list_pool()
            content = sh.list_content()
            self.local.replace_pool(pool)
            self.local.replace_content(content)
            dt = time.time() - t0
            self._status.last_pull_at = _now()
            self._status.last_error = None
            self._save_status()
            log.info("[mirror] pull 완료 — pool=%d content=%d (%.2fs)", len(pool), len(content), dt)
            return {
                "ok": True,
                "pool_count": len(pool),
                "content_count": len(content),
                "elapsed": round(dt, 2),
            }
        except Exception as e:
            self._status.last_error = f"pull 실패: {e}"
            self._save_status()
            return {"ok": False, "reason": str(e)}

    def push_to_sheets(self) -> dict:
        """Local → Sheets 일괄 동기화. 보류 중이던 변경을 한 번에 올린다."""
        sh = self._get_sheets()
        if sh is None:
            return {"ok": False, "reason": "sheets_unavailable"}

        try:
            t0 = time.time()
            pool = self.local.list_pool()
            content = self.local.list_content()
            sh.replace_pool(pool)
            sh.replace_content(content)
            dt = time.time() - t0
            self._status.last_push_at = _now()
            self._status.last_error = None
            self._status.pending_writes = 0
            self._save_status()
            log.info("[mirror] push 완료 — pool=%d content=%d (%.2fs)", len(pool), len(content), dt)
            return {
                "ok": True,
                "pool_count": len(pool),
                "content_count": len(content),
                "elapsed": round(dt, 2),
            }
        except Exception as e:
            self._status.last_error = f"push 실패: {e}"
            self._save_status()
            return {"ok": False, "reason": str(e)}

