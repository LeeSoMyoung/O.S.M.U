"""로컬 CSV 폴백 — Codespace에서 자격증명 없이도 즉시 데모 가능.

파일 형식 / 컬럼 순서는 Sheets 백엔드와 100% 동일하므로,
나중에 동일 CSV를 Google Sheets에 그대로 import 해도 호환된다.
"""
from __future__ import annotations

import csv
import os
from typing import List, Optional

from ..models import ContentRecord, KeywordPoolItem
from .base import BaseStorage


class LocalCsvStorage(BaseStorage):
    name = "local"

    def __init__(self, data_dir: str = "./data"):
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self.pool_path = os.path.join(self.data_dir, "keyword_pool.csv")
        self.content_path = os.path.join(self.data_dir, "content_db.csv")
        self._ensure_header(self.pool_path, KeywordPoolItem.HEADER)
        self._ensure_header(self.content_path, ContentRecord.HEADER)

    # ── 공통 ─────────────────────────────────────────────
    @staticmethod
    def _ensure_header(path: str, header: list) -> None:
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            with open(path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(header)

    @staticmethod
    def _read_rows(path: str) -> List[list]:
        with open(path, "r", newline="", encoding="utf-8") as f:
            rows = list(csv.reader(f))
        return rows[1:] if rows else []  # 헤더 제외

    @staticmethod
    def _write_all(path: str, header: list, rows: List[list]) -> None:
        tmp = path + ".tmp"
        with open(tmp, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
        os.replace(tmp, path)

    # ── keyword_pool ────────────────────────────────────
    def list_pool(self) -> List[KeywordPoolItem]:
        return [KeywordPoolItem.from_row(r) for r in self._read_rows(self.pool_path)]

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
        self._write_all(self.pool_path, KeywordPoolItem.HEADER, [it.to_row() for it in items])

    # ── content_db ─────────────────────────────────────
    def list_content(self) -> List[ContentRecord]:
        return [ContentRecord.from_row(r) for r in self._read_rows(self.content_path)]

    def append_content(self, record: ContentRecord) -> None:
        with open(self.content_path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(record.to_row())

    def replace_content(self, records) -> None:
        self._write_all(self.content_path, ContentRecord.HEADER, [r.to_row() for r in records])
