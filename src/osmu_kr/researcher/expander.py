"""seed → 관련 키워드 후보 생성기.

description의 첫 번째 라이프사이클 단계:
    "seed 입력을 통한 키워드 생성 단계"
    → 관련 키워드 5~10개 수집

현재는 내장 형태소 변형 규칙으로 동작.
나중에 OpenClaw → 블랙키위 / 구글 트렌드 크롤링으로 교체할 수 있도록
expand(seed) 한 함수에 책임을 격리한다.
"""
from __future__ import annotations

from typing import List

# 카테고리별 모디파이어 — 너무 많으면 노이즈, 적당히 8~12개.
INTENT_MODIFIERS = [
    "추천",
    "비교",
    "방법",
    "순위",
    "후기",
    "가격",
    "리뷰",
    "best",
    "TOP5",
]
SCOPE_MODIFIERS = [
    "직장인",
    "초보자",
    "2025",
    "단기간",
    "주말",
    "집에서",
    "20대",
    "30대",
]
QUESTION_MODIFIERS = [
    "무엇",
    "어떻게",
    "왜",
    "차이",
]


def expand(seed: str, limit: int = 10) -> List[str]:
    s = (seed or "").strip()
    if not s:
        return []

    candidates: list[str] = []
    # 1) seed 단독
    candidates.append(s)
    # 2) seed + 의도어
    for m in INTENT_MODIFIERS:
        candidates.append(f"{s} {m}")
    # 3) seed + 범위어
    for m in SCOPE_MODIFIERS:
        candidates.append(f"{m} {s}")
    # 4) seed + 의문어 (질문형)
    for q in QUESTION_MODIFIERS:
        candidates.append(f"{s} {q}")

    # dedup
    seen = set()
    unique = []
    for c in candidates:
        k = c.strip()
        if k and k not in seen:
            seen.add(k)
            unique.append(k)
    return unique[:limit]
