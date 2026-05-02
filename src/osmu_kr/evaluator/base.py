"""Evaluator 인터페이스.

description 마지막 단락의 요구사항:
    "평가 함수는 입력과 출력이 명확한 형태로 정의되어야 하며,
     외부 API 연동 시에도 동일한 인터페이스를 유지해야 한다."

→ evaluate(keyword: str) -> Evaluation 단일 진입점.
   휴리스틱이든 Naver Ads든 동일하게 호출된다.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, List

from ..models import Evaluation


class BaseEvaluator(ABC):
    name: str = "base"

    @abstractmethod
    def evaluate(self, keyword: str, *, seed: str = "") -> Evaluation: ...

    def evaluate_longtail(self, keyword: str, *, seed: str = "") -> Evaluation:
        """롱테일 변형(알케미 결과)을 더 관대하게 평가하는 모드.

        기본 구현은 일반 evaluate() 와 동일. NaverGoldenEvaluator 는
        가중치를 LONGTAIL_WEIGHTS 로 바꿔 호출한다.
        """
        return self.evaluate(keyword, seed=seed)

    def evaluate_many(self, keywords: Iterable[str], *, seed: str = "") -> List[Evaluation]:
        return [self.evaluate(k, seed=seed) for k in keywords]
