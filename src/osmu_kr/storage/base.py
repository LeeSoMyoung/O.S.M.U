"""Storage 인터페이스.

Sheets/Local 두 백엔드가 동일한 메서드 집합을 구현한다.
Researcher는 어떤 백엔드를 쓰는지 알 필요가 없다 (DI).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from ..models import ContentRecord, KeywordPoolItem


class BaseStorage(ABC):
    name: str = "base"

    # ── keyword_pool ────────────────────────────────────────
    @abstractmethod
    def list_pool(self) -> List[KeywordPoolItem]: ...

    @abstractmethod
    def get_pool(self, keyword_id: str) -> Optional[KeywordPoolItem]: ...

    @abstractmethod
    def upsert_pool(self, item: KeywordPoolItem) -> None: ...

    @abstractmethod
    def delete_pool(self, keyword_id: str) -> bool: ...

    @abstractmethod
    def replace_pool(self, items: List[KeywordPoolItem]) -> None:
        """전체 교체 (정리 단계에서 일괄 적용)."""

    # ── content_db ─────────────────────────────────────────
    @abstractmethod
    def list_content(self) -> List[ContentRecord]: ...

    @abstractmethod
    def append_content(self, record: ContentRecord) -> None: ...

    def replace_content(self, records: List[ContentRecord]) -> None:
        """content_db 통째 교체. 기본 구현은 list_content/clear 후 일괄 append.
        각 백엔드가 더 효율적인 구현을 제공할 수 있다 (예: xlsx 시트 통째 재작성).
        """
        # 기본 구현 — 비효율이지만 안전. 백엔드에서 override 권장.
        existing = self.list_content()
        if existing:
            # 단순 fallback: 모든 기존 행을 지운 뒤 다시 append.
            # CSV/XLSX/Sheets 백엔드는 각자 효율적 버전을 override한다.
            raise NotImplementedError(
                f"{type(self).__name__} 가 replace_content 를 직접 구현해야 합니다."
            )
        for r in records:
            self.append_content(r)

    # 헬퍼
    def find_pool_by_keyword(self, keyword: str) -> Optional[KeywordPoolItem]:
        kw = (keyword or "").strip().lower()
        for item in self.list_pool():
            if item.keyword.strip().lower() == kw:
                return item
        return None
