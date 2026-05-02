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

    def evaluate_many(self, keywords: Iterable[str], *, seed: str = "") -> List[Evaluation]:
        return [self.evaluate(k, seed=seed) for k in keywords]
