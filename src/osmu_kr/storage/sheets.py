"""Google Sheets 백엔드 (gspread).

자격증명/시트 ID가 제공되면 동작하고, 없으면 ImportError/Runtime 에러를 발생시킨다.
factory.build_storage()가 자동 폴백을 책임지므로 이 모듈에서는 단순히 동작/실패만 다룬다.
"""
from __future__ import annotations

from typing import List, Optional

from ..models import ContentRecord, KeywordPoolItem
from .base import BaseStorage


class SheetsStorage(BaseStorage):
    name = "sheets"

    def __init__(
        self,
        credentials_path: str,
        sheet_id: Optional[str] = None,
        sheet_title: Optional[str] = None,
        ws_keyword_pool: str = "keyword_pool",
        ws_content_db: str = "content_db",
    ):
        # 지연 import — 패키지 미설치 환경에서도 LocalCsvStorage가 동작해야 하므로
        try:
            import gspread  # type: ignore
            from google.oauth2.service_account import Credentials  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "gspread/google-auth가 설치돼 있지 않습니다. "
                "`pip install gspread google-auth`"
            ) from e

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(credentials_path, scopes=scopes)
        self._gc = gspread.authorize(creds)

        if sheet_id:
            self._sh = self._gc.open_by_key(sheet_id)
        elif sheet_title:
            try:
                self._sh = self._gc.open(sheet_title)
            except Exception:
                self._sh = self._gc.create(sheet_title)
        else:
            raise RuntimeError("sheet_id 또는 sheet_title 중 하나는 필요합니다.")

        self._ws_pool = self._ensure_ws(ws_keyword_pool, KeywordPoolItem.HEADER)
        self._ws_content = self._ensure_ws(ws_content_db, ContentRecord.HEADER)

    # ── 헬퍼 ─────────────────────────────────────────────
    def _ensure_ws(self, title: str, header: list):
        try:
            ws = self._sh.worksheet(title)
        except Exception:
            ws = self._sh.add_worksheet(title=title, rows=1000, cols=max(20, len(header)))
            ws.update("A1", [header])
            return ws
        # 헤더 보정
        first_row = ws.row_values(1)
        if first_row != header:
            ws.update("A1", [header])
        return ws

    @staticmethod
    def _rows_after_header(ws) -> List[list]:
        values = ws.get_all_values()
        return values[1:] if values else []

    # ── keyword_pool ───────────────────────────────────
    def list_pool(self) -> List[KeywordPoolItem]:
        return [KeywordPoolItem.from_row(r) for r in self._rows_after_header(self._ws_pool)]

    def get_pool(self, keyword_id: str) -> Optional[KeywordPoolItem]:
        for it in self.list_pool():
            if it.keyword_id == keyword_id:
                return it
        return None

    def upsert_pool(self, item: KeywordPoolItem) -> None:
        items = self.list_pool()
        replaced = False
        for i, it in enumerate(items):
            if it.keyword_id == item.keyword_id:
                items[i] = item
                replaced = True
                break
        if not replaced:
            items.append(item)
        self.replace_pool(items)

    def delete_pool(self, keyword_id: str) -> bool:
        items = self.list_pool()
        new_items = [it for it in items if it.keyword_id != keyword_id]
        if len(new_items) == len(items):
            return False
        self.replace_pool(new_items)
        return True

    def replace_pool(self, items: List[KeywordPoolItem]) -> None:
        self._ws_pool.clear()
        rows = [KeywordPoolItem.HEADER] + [it.to_row() for it in items]
        self._ws_pool.update("A1", rows)

    # ── content_db ────────────────────────────────────
    def list_content(self) -> List[ContentRecord]:
        return [ContentRecord.from_row(r) for r in self._rows_after_header(self._ws_content)]

    def append_content(self, record: ContentRecord) -> None:
        self._ws_content.append_row(record.to_row(), value_input_option="USER_ENTERED")

    def replace_content(self, records) -> None:
        self._ws_content.clear()
        rows = [ContentRecord.HEADER] + [r.to_row() for r in records]
        self._ws_content.update("A1", rows)
