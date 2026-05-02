"""Naver 검색광고 API Evaluator (인터페이스 stub).

지금은 실제 API 키 없이 동작하지 않지만, 동일한 BaseEvaluator 인터페이스를
구현해 두어 환경변수 OSMU_EVALUATOR=naver_ads 로 즉시 교체 가능하다.

실제 구현 시:
    POST https://api.searchad.naver.com/keywordstool
    HMAC-SHA256 서명 헤더(X-Timestamp, X-API-KEY, X-Customer, X-Signature)
    응답의 monthlyPcQcCnt + monthlyMobileQcCnt 합 → search_volume
    compIdx → 경쟁도 매핑, plAvgDepth/광고 노출 → CPC 보정

description의 요구사항: "이후 실제 광고 데이터를 기반으로 점수를 재산정할
수 있도록 구조를 열어두어야 한다." → 휴리스틱과 동일한 Evaluation을 반환.
"""
from __future__ import annotations

import os
from typing import Optional

from ..models import Evaluation
from .base import BaseEvaluator
from .heuristic import HeuristicEvaluator


class NaverAdsEvaluator(BaseEvaluator):
    name = "naver_ads"

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret: Optional[str] = None,
        customer_id: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("NAVER_AD_API_KEY")
        self.secret = secret or os.getenv("NAVER_AD_SECRET")
        self.customer_id = customer_id or os.getenv("NAVER_AD_CUSTOMER_ID")
        # 자격증명이 없으면 안전하게 휴리스틱으로 폴백한다.
        # (description: 동일 인터페이스 유지가 핵심)
        self._fallback = HeuristicEvaluator()

    @property
    def has_credentials(self) -> bool:
        return all([self.api_key, self.secret, self.customer_id])

    def evaluate(self, keyword: str, *, seed: str = "") -> Evaluation:
        if not self.has_credentials:
            ev = self._fallback.evaluate(keyword, seed=seed)
            ev.raw = {**ev.raw, "evaluator": "naver_ads(fallback→heuristic)"}
            return ev

        # ── 실제 호출 자리표시자 ──
        # data = self._call_naver_keywordstool(keyword)
        # search_volume = data["monthlyPcQcCnt"] + data["monthlyMobileQcCnt"]
        # competition = self._map_comp_idx(data["compIdx"])
        # cpc = data.get("plAvgDepth", 0)
        # ...
        # 현 단계에서는 stub 동작 — 휴리스틱 결과에 라벨만 바꿔서 반환
        ev = self._fallback.evaluate(keyword, seed=seed)
        ev.raw = {**ev.raw, "evaluator": "naver_ads(stub)"}
        return ev
