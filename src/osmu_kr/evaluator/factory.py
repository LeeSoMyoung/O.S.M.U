from __future__ import annotations

from ..config import Config
from .base import BaseEvaluator
from .heuristic import HeuristicEvaluator
from .naver_ads import NaverAdsEvaluator


def build_evaluator(cfg: Config) -> BaseEvaluator:
    name = (cfg.evaluator or "heuristic").lower()
    if name == "naver_ads":
        return NaverAdsEvaluator()
    return HeuristicEvaluator()
