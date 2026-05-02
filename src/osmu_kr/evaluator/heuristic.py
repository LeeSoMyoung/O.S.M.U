"""휴리스틱 평가기.

기획서 §6-1의 황금 키워드 기준을 코드로 옮긴 것.
- 월 검색량  : 1,000~30,000 구간이 만점 (장꼬리/롱테일)
- 경쟁도(KD) : 낮음 가산 / 중간·높음 감점
- CPC        : 500원 이상 가산
- 상업적 의도: 추천/비교/방법/순위/리뷰/best/top 포함 시 가산

각 키워드 문자열에 대해 결정적인(=재현 가능한) 점수를 만든다.
md5 해시를 시드로 써서 데모/테스트가 흔들리지 않도록 한다.
"""
from __future__ import annotations

import hashlib
from typing import Tuple

from ..models import Evaluation
from .base import BaseEvaluator

COMMERCIAL_KEYWORDS = (
    "추천",
    "비교",
    "방법",
    "순위",
    "리뷰",
    "후기",
    "가격",
    "가성비",
    "best",
    "top",
    "vs",
    "차이",
)
COMPETITIONS = ("낮음", "중간", "높음")


class HeuristicEvaluator(BaseEvaluator):
    name = "heuristic"

    @staticmethod
    def _seeded_floats(keyword: str) -> Tuple[float, float, float]:
        """키워드 문자열로부터 3개의 0~1 결정값을 생성."""
        h = hashlib.md5(keyword.encode("utf-8")).hexdigest()
        a = int(h[0:8], 16) / 0xFFFFFFFF
        b = int(h[8:16], 16) / 0xFFFFFFFF
        c = int(h[16:24], 16) / 0xFFFFFFFF
        return a, b, c

    def evaluate(self, keyword: str, *, seed: str = "") -> Evaluation:
        kw = (keyword or "").strip()
        if not kw:
            return Evaluation()

        a, b, c = self._seeded_floats(kw)

        # 검색량: 200 ~ 50,000 사이에서 분포 (대수 분포 비슷하게)
        # 길이가 길수록(=롱테일) 검색량이 줄도록 보정
        token_len = len(kw.replace(" ", ""))
        length_factor = max(0.3, 1.0 - (token_len / 30.0))
        search_volume = int(200 + a * 49_800 * length_factor)

        # 경쟁도: 길이가 길수록 낮음(롱테일이라), 짧으면 높음 경향
        if token_len <= 4:
            comp_idx = 2 if b > 0.4 else 1
        elif token_len <= 8:
            comp_idx = 1 if b > 0.5 else 0
        else:
            comp_idx = 0 if b > 0.3 else 1
        competition = COMPETITIONS[comp_idx]

        # CPC: 200~2000원
        cpc = round(200 + c * 1800, -1)

        # 상업적 의도: 키워드에 의도 단어가 있으면 부스트
        commercial_intent = sum(1 for w in COMMERCIAL_KEYWORDS if w in kw.lower())
        commercial_intent = min(1.0, 0.2 + commercial_intent * 0.25)

        # ── 황금 점수 (0~100) ────────────────────────────
        # 검색량 점수 (1k~30k 만점)
        if 1000 <= search_volume <= 30_000:
            sv_score = 30.0
        elif search_volume < 1000:
            sv_score = max(0.0, 30.0 * (search_volume / 1000.0))
        else:  # 너무 큰 검색량 = 빅키워드 (감점)
            over = (search_volume - 30_000) / 20_000.0
            sv_score = max(10.0, 30.0 - over * 15.0)

        # 경쟁도 점수
        comp_score = {"낮음": 30.0, "중간": 15.0, "높음": 5.0}[competition]

        # CPC 점수 (500원 이상부터 가산)
        cpc_score = min(20.0, max(0.0, (cpc - 200) / 1800 * 20.0))
        if cpc >= 500:
            cpc_score = max(cpc_score, 12.0)

        # 상업적 의도 점수
        intent_score = commercial_intent * 20.0

        score = round(sv_score + comp_score + cpc_score + intent_score, 2)

        return Evaluation(
            search_volume=search_volume,
            competition=competition,
            cpc=cpc,
            commercial_intent=commercial_intent,
            score=score,
            raw={
                "sv_score": round(sv_score, 2),
                "comp_score": comp_score,
                "cpc_score": round(cpc_score, 2),
                "intent_score": round(intent_score, 2),
                "evaluator": self.name,
                "seed": seed,
            },
        )
