"""KeywordResearcher 본체.

라이프사이클(요구사항 매핑):
  1. CREATE   : run_seed(seed)   — seed 입력 → 후보 → 평가 → pool 저장 (+연금술)
  2. UPDATE   : alchemize 자동 적용 (manager.prune 내부 + run_seed 내부)
  3. CHECK+CREATE : check_keyword(keyword) — 사용자가 직접 입력한 키워드를 평가하여 황금이면 pool에 등록
  4. DELETE/UPDATE : prune() — POOL_MAX_SIZE / REVIVAL_DAYS 관리
  5. RECOMMEND : recommend() — seed 간격 제어 + 연속 주제 회피
  6. SELECT   : select_for_content(keyword_id, ...) — pool에서 제거 + content_db에 사용 이력 기록
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

from ..config import Config
from ..evaluator import build_evaluator
from ..evaluator.base import BaseEvaluator
from ..models import (
    STATUS_GOLDEN,
    STATUS_MEDIUM,
    STATUS_REJECTED,
    ContentRecord,
    Evaluation,
    KeywordPoolItem,
    now_utc,
    to_iso,
)
from ..storage import BaseStorage, build_storage
from . import alchemist, expander, manager, recommender

log = logging.getLogger(__name__)


@dataclass
class SeedRunReport:
    seed: str
    expanded: int = 0
    accepted: int = 0
    transmuted: int = 0
    rejected: int = 0
    items: List[KeywordPoolItem] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"seed='{self.seed}' expanded={self.expanded} "
            f"accepted={self.accepted} transmuted={self.transmuted} rejected={self.rejected}"
        )


class KeywordResearcher:
    def __init__(
        self,
        cfg: Optional[Config] = None,
        storage: Optional[BaseStorage] = None,
        evaluator: Optional[BaseEvaluator] = None,
    ):
        self.cfg = cfg or Config()
        self.storage = storage or build_storage(self.cfg)
        self.evaluator = evaluator or build_evaluator(self.cfg)
        log.info(
            "KeywordResearcher ready (storage=%s evaluator=%s)",
            self.storage.name,
            self.evaluator.name,
        )

    # ── ID helpers ─────────────────────────────────────
    def _next_keyword_id(self, extra: List[KeywordPoolItem] | None = None) -> str:
        existing = self.storage.list_pool() + (extra or [])
        nums = []
        for it in existing:
            try:
                nums.append(int(it.keyword_id))
            except (TypeError, ValueError):
                pass
        n = (max(nums) if nums else 0) + 1
        return f"{n:04d}"

    def _next_content_id(self) -> str:
        existing = self.storage.list_content()
        nums = []
        for r in existing:
            try:
                nums.append(int(r.id))
            except (TypeError, ValueError):
                pass
        n = (max(nums) if nums else 0) + 1
        return f"{n:03d}"

    # ── 1) CREATE — seed 기반 ──────────────────────────
    def run_seed(self, seed: str, *, expand_limit: int = 10) -> SeedRunReport:
        seed = (seed or "").strip()
        report = SeedRunReport(seed=seed)
        if not seed:
            return report

        candidates = expander.expand(seed, limit=expand_limit)
        report.expanded = len(candidates)

        accepted_buf: list[KeywordPoolItem] = []

        for kw in candidates:
            # 이미 풀에 같은 keyword가 있으면 스킵
            if self.storage.find_pool_by_keyword(kw):
                continue

            ev: Evaluation = self.evaluator.evaluate(kw, seed=seed)

            if ev.score >= self.cfg.golden_threshold:
                item = self._build_pool_item(seed, kw, ev, accepted_buf)
                accepted_buf.append(item)
                report.items.append(item)
                report.accepted += 1
            elif self.cfg.medium_lower <= ev.score < self.cfg.medium_upper:
                # 키워드 연금술 — 변형 후보 평가 → 황금이면 추가
                added_any = False
                for variant in alchemist.transmute(kw):
                    if self.storage.find_pool_by_keyword(variant):
                        continue
                    v_ev = self.evaluator.evaluate(variant, seed=seed)
                    if v_ev.score >= self.cfg.golden_threshold:
                        item = self._build_pool_item(
                            seed, variant, v_ev, accepted_buf, source_suffix="+alchemy",
                            note=f"transmuted from '{kw}'",
                        )
                        accepted_buf.append(item)
                        report.items.append(item)
                        report.transmuted += 1
                        added_any = True
                if not added_any:
                    report.rejected += 1
            else:
                report.rejected += 1

        # 일괄 upsert
        for it in accepted_buf:
            self.storage.upsert_pool(it)

        log.info("run_seed: %s", report.summary())

        # 풀 크기 즉시 정리 (REVIVAL은 prune()에서)
        self._enforce_max_size()
        return report

    def _build_pool_item(
        self,
        seed: str,
        keyword: str,
        ev: Evaluation,
        extra: List[KeywordPoolItem],
        source_suffix: str = "",
        note: str = "",
    ) -> KeywordPoolItem:
        return KeywordPoolItem(
            keyword_id=self._next_keyword_id(extra),
            seed_keyword=seed,
            keyword=keyword,
            search_volume=ev.search_volume,
            competition=ev.competition,
            cpc=ev.cpc,
            commercial_intent=ev.commercial_intent,
            score=ev.score,
            status=STATUS_GOLDEN,
            source=f"{self.evaluator.name}{source_suffix}",
            note=note,
        )

    def _enforce_max_size(self) -> None:
        pool = self.storage.list_pool()
        if len(pool) <= self.cfg.pool_max_size:
            return
        pool.sort(key=lambda x: x.score, reverse=True)
        kept = pool[: self.cfg.pool_max_size]
        self.storage.replace_pool(kept)
        log.info("max_size 정리: %d → %d", len(pool), len(kept))

    # ── 3) CHECK + CREATE — 사용자 직접 입력 ──────────────
    def check_keyword(self, keyword: str, *, seed: Optional[str] = None) -> KeywordPoolItem:
        keyword = (keyword or "").strip()
        if not keyword:
            raise ValueError("keyword 가 비어 있습니다.")

        seed = (seed or keyword).strip()  # seed 미지정이면 자기 자신을 seed로

        existing = self.storage.find_pool_by_keyword(keyword)
        ev = self.evaluator.evaluate(keyword, seed=seed)

        if existing:
            existing.search_volume = ev.search_volume
            existing.competition = ev.competition
            existing.cpc = ev.cpc
            existing.commercial_intent = ev.commercial_intent
            existing.score = ev.score
            existing.updated_at = to_iso(now_utc())
            existing.status = (
                STATUS_GOLDEN if ev.score >= self.cfg.golden_threshold else STATUS_MEDIUM
            )
            self.storage.upsert_pool(existing)
            return existing

        status = (
            STATUS_GOLDEN
            if ev.score >= self.cfg.golden_threshold
            else (STATUS_MEDIUM if ev.score >= self.cfg.medium_lower else STATUS_REJECTED)
        )
        item = KeywordPoolItem(
            keyword_id=self._next_keyword_id(),
            seed_keyword=seed,
            keyword=keyword,
            search_volume=ev.search_volume,
            competition=ev.competition,
            cpc=ev.cpc,
            commercial_intent=ev.commercial_intent,
            score=ev.score,
            status=status,
            source=f"{self.evaluator.name}/manual",
            note="user-checked",
        )
        if status != STATUS_REJECTED:
            self.storage.upsert_pool(item)
        return item

    # ── 4) PRUNE ────────────────────────────────────────
    def prune(self):
        return manager.prune(self.storage, self.evaluator, self.cfg)

    # ── 5) RECOMMEND ────────────────────────────────────
    def recommend(self, top_n: int = 5) -> List[KeywordPoolItem]:
        return recommender.recommend(self.storage, self.cfg, top_n=top_n)

    # ── 6) SELECT (pool → content_db로 이동) ──────────────
    def select_for_content(
        self,
        keyword_id: str,
        *,
        original_source: str = "",
        title_final: str = "",
    ) -> ContentRecord:
        item = self.storage.get_pool(keyword_id)
        if not item:
            raise KeyError(f"keyword_id={keyword_id}가 pool에 없습니다.")

        # seed 간격 제어 — 동일 seed가 cooldown 안에 있으면 차단
        blocked = recommender._seeds_in_cooldown(  # type: ignore[attr-defined]
            self.storage.list_content(), self.cfg.seed_cooldown_days
        )
        if item.seed_keyword in blocked:
            raise PermissionError(
                f"seed_cooldown 위반: '{item.seed_keyword}' 는 최근 "
                f"{self.cfg.seed_cooldown_days}일 내에 사용됨"
            )

        record = ContentRecord(
            id=self._next_content_id(),
            keyword=item.keyword,
            seed_keyword=item.seed_keyword,
            keyword_id=item.keyword_id,
            original_source=original_source,
            status="대기중",
            title_final=title_final,
            created_at=to_iso(now_utc()),
            note=f"selected from pool (score={item.score})",
        )
        self.storage.append_content(record)
        # 추천한 키워드를 pool에서 제거
        self.storage.delete_pool(keyword_id)
        return record
