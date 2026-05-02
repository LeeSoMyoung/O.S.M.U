"""키워드 연금술 (Keyword Alchemy).

description의 두 번째 라이프사이클 단계:
    "보통 수준 키워드를 단순히 버리지 않고 변형해 가치 있는 키워드로 재가공"
    예) '다이어트' → '단기간 다이어트 식단' / '직장인 다이어트 방법'

핵심 아이디어:
    원 키워드의 점수가 medium이면, 의도어/범위어를 한두 개 더 붙여서
    경쟁도를 떨어뜨리고 상업적 의도를 높인 변형을 만든다.
"""
from __future__ import annotations

import itertools
from typing import List

ALCHEMY_INTENT = ["추천", "방법", "비교", "TOP5", "순위", "후기"]
ALCHEMY_SCOPE = ["직장인", "초보자", "단기간", "2025", "집에서", "주말"]


def transmute(keyword: str, max_variants: int = 3) -> List[str]:
    """medium 키워드를 long-tail 변형으로 재가공."""
    base = (keyword or "").strip()
    if not base:
        return []

    out: list[str] = []

    # 1) 범위 + 키워드 + 의도 (가장 정확한 long-tail)
    for scope, intent in itertools.product(ALCHEMY_SCOPE, ALCHEMY_INTENT):
        out.append(f"{scope} {base} {intent}")
        if len(out) >= max_variants * 4:  # 후보를 충분히 만든 뒤 잘라낼 거라 여유 있게
            break

    # 2) 키워드 + 의도 (범위 빠진 버전)
    for intent in ALCHEMY_INTENT:
        out.append(f"{base} {intent}")

    # dedup, 원 키워드 제외
    seen, unique = set(), []
    for c in out:
        c = c.strip()
        if c and c != base and c not in seen:
            seen.add(c)
            unique.append(c)

    return unique[:max_variants]
