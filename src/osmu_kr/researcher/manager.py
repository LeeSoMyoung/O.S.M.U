"""풀 관리(prune) — POOL_MAX_SIZE / REVIVAL_DAYS 정책.

description 네 번째 단계:
    "POOL_MAX_SIZE — 저장 가능한 최대 키워드 수"
    "REVIVAL_DAYS — 키워드의 유효기간"
    "일정 기간이 지난 키워드는 재평가되거나 삭제된다."

전략:
    1) REVIVAL_DAYS를 초과한 항목은 재평가한다.
       - 재평가 점수가 황금 임계치 이상이면 status=golden 유지 + updated_at 갱신
       - medium 범위면 키워드 연금술로 변형 후 추가
       - 그 미만이면 status=expired 마킹 후 제거
    2) 위 단계 후에도 풀 크기가 POOL_MAX_SIZE를 초과하면 score 낮은 항목부터 제거.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import List, Tuple

from ..config import Config
from ..evaluator.base import BaseEvaluator
from ..models import (
    STATUS_EXPIRED,
    STATUS_GOLDEN,
    STATUS_MEDIUM,
    Evaluation,
    KeywordPoolItem,
    from_iso,
    now_utc,
    to_iso,
)
from ..storage.base import BaseStorage
from . import alchemist

log = logging.getLogger(__name__)


@dataclass
class PruneReport:
    revaluated: int = 0
    refreshed: int = 0  # 재평가 후 살아남음
    expired: int = 0    # REVIVAL_DAYS 초과 + 점수 미달로 삭제
    transmuted: int = 0  # medium → 연금술로 변형 추가
    overflow_removed: int = 0  # POOL_MAX_SIZE 초과로 제거

    def summary(self) -> str:
        return (
            f"revaluated={self.revaluated} refreshed={self.refreshed} "
            f"expired={self.expired} transmuted={self.transmuted} "
            f"overflow_removed={self.overflow_removed}"
        )


def prune(
    storage: BaseStorage, evaluator: BaseEvaluator, cfg: Config
) -> Tuple[List[KeywordPoolItem], PruneReport]:
    items = storage.list_pool()
    report = PruneReport()
    now = now_utc()
    cutoff = now - timedelta(days=cfg.revival_days)

    survivors: list[KeywordPoolItem] = []
    new_variants: list[KeywordPoolItem] = []

    for it in items:
        created_at = from_iso(it.updated_at or it.created_at)
        if created_at >= cutoff:
            survivors.append(it)
            continue

        # ── REVIVAL 초과 → 재평가 ──
        report.revaluated += 1
        ev: Evaluation = evaluator.evaluate(it.keyword, seed=it.seed_keyword)

        if ev.score >= cfg.golden_threshold:
            it.search_volume = ev.search_volume
            it.competition = ev.competition
            it.cpc = ev.cpc
            it.commercial_intent = ev.commercial_intent
            it.score = ev.score
            it.status = STATUS_GOLDEN
            it.updated_at = to_iso(now)
            it.note = (it.note + " | re-evaluated:golden").strip(" |")
            survivors.append(it)
            report.refreshed += 1
        elif cfg.medium_lower <= ev.score < cfg.medium_upper:
            # 연금술 시도 — 변형 후보를 추가, 원본은 만료
            for variant in alchemist.transmute(it.keyword):
                v_ev = evaluator.evaluate(variant, seed=it.seed_keyword)
                if v_ev.score >= cfg.golden_threshold:
                    nv = KeywordPoolItem(
                        keyword_id=_next_id(items + survivors + new_variants),
                        seed_keyword=it.seed_keyword,
                        keyword=variant,
                        **v_ev.to_row(),
                        status=STATUS_GOLDEN,
                        source=f"{evaluator.name}+alchemy",
                        note=f"transmuted from '{it.keyword}'",
                    )
                    new_variants.append(nv)
                    report.transmuted += 1
            report.expired += 1  # 원본은 제거
        else:
            it.status = STATUS_EXPIRED
            report.expired += 1

    pool = survivors + new_variants

    # ── POOL_MAX_SIZE 초과 처리 ──
    if len(pool) > cfg.pool_max_size:
        pool.sort(key=lambda x: x.score, reverse=True)
        report.overflow_removed = len(pool) - cfg.pool_max_size
        pool = pool[: cfg.pool_max_size]

    storage.replace_pool(pool)
    log.info("prune complete: %s", report.summary())
    return pool, report


def _next_id(existing: list[KeywordPoolItem]) -> str:
    nums = []
    for it in existing:
        try:
            nums.append(int(it.keyword_id))
        except (TypeError, ValueError):
            pass
    n = (max(nums) if nums else 0) + 1
    return f"{n:04d}"
