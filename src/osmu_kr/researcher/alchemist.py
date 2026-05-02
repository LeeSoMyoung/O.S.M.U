"""키워드 연금술 (v2 — golden_keyword.py 의 처방형 로직 통합).

[ 처방 카테고리 ]
  · 상업의도_부족 → 상업 수식어 (추천/비교/후기…)
  · 경쟁도_높음   → 대상/상황/가격/기간 수식어 (직장인/초보자/가성비…)
  · 트렌드_낮음   → 목적/시의성 수식어 (2026년/내돈내산/실패 없는…)

[ 두 가지 호출 방식 ]
  · transmute(keyword, max_variants)            : 약점 정보 없을 때 — 모든 처방 사용 (후방 호환)
  · transmute_with_diagnosis(keyword, weak, n)  : 약점 진단 결과를 받아 처방형 변형
"""
from __future__ import annotations

import itertools
from typing import List, Sequence

# ── 수식어 뱅크 (golden_keyword.py 와 동일) ───────────
ALCHEMY_TEMPLATES = {
    "상업의도": [
        "추천", "비교", "후기", "순위", "방법", "장단점",
        "리뷰", "효과", "선택 방법", "어떻게 하나요",
        "잘하는 법", "잘 고르는 법",
    ],
    "대상": [
        "대학생", "직장인", "사회초년생", "30대", "40대", "50대",
        "주부", "자취생", "초보자", "여성", "남성",
        "임산부", "중년 여성", "시니어",
    ],
    "상황": [
        "처음 시작하는", "혼자서", "집에서", "10분 만에",
        "간단하게", "입문", "바쁜 직장인을 위한",
        "운동 없이", "식단만으로", "꾸준히 하는",
        "주말에", "아침에",
    ],
    "가격": [
        "가성비", "저렴하게", "무료로", "저예산",
        "비용 없이", "돈 안 드는", "월 1만원으로",
    ],
    "목적": [
        "선물용", "내돈내산 후기", "실사용 후기",
        "2026년", "최신", "효과 좋은",
        "실패 없는", "검증된",
    ],
    "기간": [
        "1주일", "한 달", "3개월 만에",
        "빠르게", "단기간에", "꾸준히",
    ],
}


def _dedup_against(keyword: str, candidates: Sequence[str]) -> List[str]:
    """원본과 의미적 중복(공백제거+소문자) 제거."""
    orig_norm = keyword.replace(" ", "").lower()
    seen_surface, seen_norm = {keyword}, {orig_norm}
    out = []
    for c in candidates:
        c = " ".join((c or "").split())
        norm = c.replace(" ", "").lower()
        if c and c not in seen_surface and norm not in seen_norm:
            seen_surface.add(c)
            seen_norm.add(norm)
            out.append(c)
    return out


def transmute(keyword: str, max_variants: int = 3) -> List[str]:
    """후방 호환 진입점 — 약점 정보 없으면 모든 처방을 균등하게 시도."""
    base = (keyword or "").strip()
    if not base:
        return []
    weaknesses = ["상업의도_부족", "경쟁도_높음", "트렌드_낮음"]
    return transmute_with_diagnosis(base, weaknesses, max_variants=max_variants)


def transmute_with_diagnosis(
    keyword: str,
    weaknesses: Sequence[str],
    max_variants: int = 10,
) -> List[str]:
    """약점 진단 결과에 맞춰 처방형 변형 키워드 생성.

    weaknesses 후보:
      - "상업의도_부족" / "경쟁도_높음" / "트렌드_낮음"
    """
    base = (keyword or "").strip()
    if not base:
        return []

    cands: list[str] = []

    if "상업의도_부족" in weaknesses:
        for mod in ALCHEMY_TEMPLATES["상업의도"][:6]:
            cands.append(f"{base} {mod}")

    if "경쟁도_높음" in weaknesses:
        for mod in ALCHEMY_TEMPLATES["대상"][:5]:
            cands.append(f"{mod} {base}")
        for mod in ALCHEMY_TEMPLATES["상황"][:4]:
            cands.append(f"{base} {mod}")
        for mod in ALCHEMY_TEMPLATES["가격"][:3]:
            cands.append(f"{mod} {base}")
        for mod in ALCHEMY_TEMPLATES["기간"][:2]:
            cands.append(f"{base} {mod}")

    if "트렌드_낮음" in weaknesses:
        for mod in ALCHEMY_TEMPLATES["목적"][:4]:
            cands.append(f"{base} {mod}")
        for mod in ALCHEMY_TEMPLATES["기간"][:2]:
            cands.append(f"{base} {mod}")

    return _dedup_against(base, cands)[:max_variants]
