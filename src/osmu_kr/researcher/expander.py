"""seed → 관련 키워드 후보 생성기 (v2 — golden_keyword.py 로직 통합).

전략:
  ① 네이버 자동완성 API (인증 불필요, 비공식 — 실패 시 graceful fallback)
  ② 접미어 조합 확장 (추천/방법/비교/후기/가격/순위/장단점/효과/종류/주의사항)
  ③ 표면 + 정규화(공백제거+소문자) 이중 중복 제거
"""
from __future__ import annotations

import logging
from typing import List

log = logging.getLogger(__name__)

# 사용자 제공 golden_keyword.py 의 EXPANSION_SUFFIXES 와 동일
EXPANSION_SUFFIXES = [
    "추천", "방법", "비교", "후기", "가격",
    "순위", "장단점", "효과", "종류", "주의사항",
]

# (선택) 후방 호환 — 기존 노출됐던 변수명 유지
INTENT_MODIFIERS = ["추천", "비교", "방법", "순위", "후기", "가격", "리뷰", "best", "TOP5"]
SCOPE_MODIFIERS = ["직장인", "초보자", "2025", "단기간", "주말", "집에서", "20대", "30대"]
QUESTION_MODIFIERS = ["무엇", "어떻게", "왜", "차이"]


def fetch_naver_autocomplete(seed: str, limit: int = 10) -> List[str]:
    """네이버 자동완성 — 인증 불필요. 실패 시 빈 리스트."""
    try:
        import requests  # 지연 import
    except ImportError:
        return []
    url = "https://ac.search.naver.com/nx/ac"
    params = {
        "q": seed, "q_enc": "utf-8", "st": "111",
        "frm": "nv", "r_format": "json", "r_enc": "utf-8",
    }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.naver.com",
    }
    try:
        r = requests.get(url, params=params, headers=headers, timeout=8)
        r.raise_for_status()
        data = r.json()
        items = data.get("items", [[]])
        if not items or not items[0]:
            return []
        results = [it[0] for it in items[0] if it and it[0].strip()]
        return results[:limit]
    except Exception as e:
        log.info("[expander] 네이버 자동완성 실패 (정상 폴백): %s", e)
        return []


def _dedup_with_normalize(candidates: list[str]) -> list[str]:
    """표면 + 정규화(공백제거+소문자) 이중 중복 제거 — ‘다이어트방법’과 ‘다이어트 방법’ 동일 처리."""
    seen_surface, seen_norm, out = set(), set(), []
    for kw in candidates:
        kw = " ".join((kw or "").split())  # 공백 정규화
        norm = kw.replace(" ", "").lower()
        if kw and kw not in seen_surface and norm not in seen_norm:
            seen_surface.add(kw)
            seen_norm.add(norm)
            out.append(kw)
    return out


def expand(seed: str, limit: int = 10, *, use_autocomplete: bool = True) -> List[str]:
    """씨앗 → 후보 키워드 (자동완성 + 접미어 조합 + 정규화 중복 제거)."""
    s = (seed or "").strip()
    if not s:
        return []

    autocomplete: list[str] = []
    if use_autocomplete:
        autocomplete = fetch_naver_autocomplete(s, limit=10)

    suffix_keywords = [f"{s} {sfx}" for sfx in EXPANSION_SUFFIXES]

    all_candidates = [s] + autocomplete + suffix_keywords
    unique = _dedup_with_normalize(all_candidates)
    return unique[:limit]
