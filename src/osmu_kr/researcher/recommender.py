"""추천기.

description 마지막 라이프사이클(추천):
    "keyword_pool에서 가장 가치 있는 키워드를 추천하고,
     사용자가 이를 선택하여 글을 작성하면 해당 키워드는 pool에서 제거된다.
     이때 반드시 고려해야 할 조건은 '최근 작성된 글과 연속되지 않는 주제'여야 한다."

또한 description의 두 번째 축(완성 기준):
    "동일 seed 키워드 기반 콘텐츠의 생성 간격을 제어"
    예) 10/3에 '다이어트' seed로 글을 썼다면 10/7에 같은 seed로 또 쓰지 않게 한다.
        → seed_cooldown_days 정책으로 차단.
"""
from __future__ import annotations

from datetime import timedelta
from typing import List, Optional

from ..config import Config
from ..models import ContentRecord, KeywordPoolItem, from_iso, now_utc
from ..storage.base import BaseStorage


def _last_seed(records: List[ContentRecord]) -> Optional[str]:
    if not records:
        return None
    # created_at 기준 최신
    latest = max(records, key=lambda r: r.created_at or "")
    return (latest.seed_keyword or "").strip()


def _seeds_in_cooldown(records: List[ContentRecord], cooldown_days: float) -> set[str]:
    cutoff = now_utc() - timedelta(days=cooldown_days)
    seeds = set()
    for r in records:
        if not r.seed_keyword:
            continue
        try:
            ts = from_iso(r.created_at)
        except Exception:
            continue
        if ts >= cutoff:
            seeds.add(r.seed_keyword.strip())
    return seeds


def recommend(
    storage: BaseStorage, cfg: Config, top_n: int = 5
) -> List[KeywordPoolItem]:
    pool = storage.list_pool()
    contents = storage.list_content()

    blocked = _seeds_in_cooldown(contents, cfg.seed_cooldown_days)
    last = _last_seed(contents) if cfg.avoid_consecutive_topic else None

    def is_eligible(item: KeywordPoolItem) -> bool:
        if item.status not in ("golden",):
            return False
        if item.seed_keyword in blocked:
            return False
        if last and item.seed_keyword == last:
            return False
        return True

    eligible = [it for it in pool if is_eligible(it)]
    # 점수 내림차순
    eligible.sort(key=lambda x: x.score, reverse=True)
    return eligible[:top_n]
