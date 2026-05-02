"""NaverGoldenEvaluator — 사용자 제공 황금 키워드 분석기 로직 통합.

[ 기준 (총 100점) ]
  1. Naver DataLab 트렌드   : 40점  (네이버 내 검색 인기도, 0~100 상대 점수 + 상승/하락 보정)
  2. Naver Blog 결과 수      : 30점  (경쟁도 역산 — very_low/low/medium/high/redocean)
  3. 상업적 의도            : 20점  (키워드 내 ‘추천/비교/방법…’ 단어 매칭)
  4. Google Trends           : 10점  (보조 — pytrends, rate limit 우려로 상위만 조회 권장)

[ 두 가지 가중치 프로필 ]
  · DEFAULT  (일반 키워드)   : 40/30/20/10
  · LONGTAIL (알케미 변형)   : 20/45/25/10  ← 트렌드는 낮아도 경쟁이 없으면 가치 있다는 가정

[ 자격증명 자동 폴백 ]
  네이버 키 / pytrends 가 없으면 부분적으로 휴리스틱(HeuristicEvaluator)으로 폴백.
  매번 import 시점에 깨지지 않게 모든 외부 호출을 try/except 로 감싼다.

[ BaseEvaluator 인터페이스 준수 ]
  · evaluate(keyword, *, seed='')         → 일반 프로필 점수
  · evaluate_longtail(keyword, *, seed='')→ 롱테일 프로필 점수 (알케미 전용)
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import datetime, timedelta
from typing import Optional

from ..models import Evaluation
from .base import BaseEvaluator
from .heuristic import HeuristicEvaluator

log = logging.getLogger(__name__)

# ── 점수표 / 임계 ─────────────────────────────────────
COMMERCIAL_WORDS = (
    "추천", "비교", "방법", "가격", "후기", "리뷰", "구매", "순위",
    "장단점", "효과", "종류", "선택", "어떻게", "최고", "베스트",
)
BLOG_COMP = {
    "very_low": 5_000,    # 30점
    "low":      30_000,   # 20점
    "medium":   100_000,  # 10점
    "high":     500_000,  # 5점
}                          # 초과: 0점

DEFAULT_WEIGHTS = {"datalab": 40, "blog_comp": 30, "commercial": 20, "gtrends": 10}
LONGTAIL_WEIGHTS = {"datalab": 20, "blog_comp": 45, "commercial": 25, "gtrends": 10}


# ── 외부 API 호출 (모두 안전 폴백) ──────────────────────
def _fetch_datalab(keyword: str, client_id: str, client_secret: str) -> dict:
    """네이버 DataLab — 최근 90일 주별 상대 트렌드(0~100). 자격증명 없으면 ‘데이터없음’."""
    if not client_id or not client_secret:
        return {"trend_score": 0, "trend_direction": "데이터없음", "source": "datalab(스킵)"}

    try:
        import requests  # 지연 import
    except ImportError:
        return {"trend_score": 0, "trend_direction": "데이터없음", "source": "datalab(requests 미설치)"}

    end = datetime.now()
    start = end - timedelta(days=90)
    body = {
        "startDate": start.strftime("%Y-%m-%d"),
        "endDate": end.strftime("%Y-%m-%d"),
        "timeUnit": "week",
        "keywordGroups": [{"groupName": keyword, "keywords": [keyword]}],
    }
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
        "Content-Type": "application/json",
    }
    try:
        r = requests.post(
            "https://openapi.naver.com/v1/datalab/search",
            headers=headers, data=json.dumps(body), timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        periods = data.get("results", [{}])[0].get("data", [])
        if not periods:
            return {"trend_score": 0, "trend_direction": "데이터없음", "source": "naver_datalab"}
        scores = [p.get("ratio", 0) for p in periods]
        avg = round(sum(scores) / len(scores), 1) if scores else 0
        recent = scores[-4:]
        older = scores[:-4] if len(scores) > 4 else scores[: max(1, len(scores) // 2)]
        recent_avg = round(sum(recent) / max(1, len(recent)), 1)
        older_avg = sum(older) / max(1, len(older))
        if recent_avg > older_avg * 1.2:
            direction = "상승중"
        elif recent_avg < older_avg * 0.8:
            direction = "하락중"
        else:
            direction = "유지중"
        return {"trend_score": avg, "trend_direction": direction, "source": "naver_datalab"}
    except Exception as e:
        log.warning("[naver_golden] DataLab 실패 [%s]: %s", keyword, e)
        return {"trend_score": 0, "trend_direction": "조회실패", "source": "naver_datalab"}


def _fetch_blog(keyword: str, client_id: str, client_secret: str) -> dict:
    """네이버 블로그 검색 — 결과 수 → 경쟁도 라벨/원점수(0~30) 반환."""
    if not client_id or not client_secret:
        return {"total_results": None, "competition_label": "데이터없음",
                "competition_score": 15, "source": "blog(스킵)"}

    try:
        import requests
    except ImportError:
        return {"total_results": None, "competition_label": "requests 미설치",
                "competition_score": 15, "source": "blog(requests 미설치)"}

    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret,
    }
    params = {"query": keyword, "display": 5, "sort": "sim"}
    try:
        r = requests.get(
            "https://openapi.naver.com/v1/search/blog.json",
            headers=headers, params=params, timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        total = data.get("total", 0)
        if total < BLOG_COMP["very_low"]:
            score, label = 30, "매우 낮음"
        elif total < BLOG_COMP["low"]:
            score, label = 20, "낮음"
        elif total < BLOG_COMP["medium"]:
            score, label = 10, "보통"
        elif total < BLOG_COMP["high"]:
            score, label = 5, "높음"
        else:
            score, label = 0, "매우 높음(레드오션)"
        return {
            "total_results": total,
            "competition_label": label,
            "competition_score": score,
            "source": "naver_blog",
        }
    except Exception as e:
        log.warning("[naver_golden] Blog 실패 [%s]: %s", keyword, e)
        return {"total_results": None, "competition_label": "조회실패",
                "competition_score": 15, "source": "blog(실패)"}


def _fetch_trends(keyword: str, enabled: bool = True) -> dict:
    """Google Trends (pytrends) — 최근 3개월 한국 기준 상대 트렌드."""
    if not enabled:
        return {"trend_score": 0, "trend_direction": "스킵", "source": "skipped"}
    try:
        from pytrends.request import TrendReq  # type: ignore

        if not hasattr(_fetch_trends, "_pytrends"):
            _fetch_trends._pytrends = TrendReq(  # type: ignore[attr-defined]
                hl="ko", tz=540, timeout=(10, 25), retries=1, backoff_factor=1.5,
            )
        pt = _fetch_trends._pytrends  # type: ignore[attr-defined]
        pt.build_payload([keyword], timeframe="today 3-m", geo="KR")
        df = pt.interest_over_time()
        if df.empty or keyword not in df.columns:
            return {"trend_score": 0, "trend_direction": "데이터없음", "source": "google_trends"}
        scores = df[keyword].tolist()
        avg = round(sum(scores) / len(scores), 1) if scores else 0
        recent = scores[-4:]
        older = scores[:-4] if len(scores) > 4 else scores[: max(1, len(scores) // 2)]
        ra = sum(recent) / max(1, len(recent))
        oa = sum(older) / max(1, len(older))
        if ra > oa * 1.2:
            direction = "상승중"
        elif ra < oa * 0.8:
            direction = "하락중"
        else:
            direction = "유지중"
        return {"trend_score": avg, "trend_direction": direction, "source": "google_trends"}
    except ImportError:
        return {"trend_score": 0, "trend_direction": "데이터없음", "source": "pytrends 미설치"}
    except Exception as e:
        log.warning("[naver_golden] Trends 실패 [%s]: %s", keyword, e)
        return {"trend_score": 0, "trend_direction": "조회실패", "source": "google_trends"}


# ── 점수 계산 ─────────────────────────────────────────
def _score(keyword: str, dl: dict, blog: dict, gt: dict, weights: dict) -> dict:
    w_dl = weights["datalab"]
    w_bl = weights["blog_comp"]
    w_co = weights["commercial"]
    w_gt = weights["gtrends"]

    # ── DataLab ──
    dl_raw = dl.get("trend_score", 0)
    dl_dir = dl.get("trend_direction", "")
    dl_src = dl.get("source", "")
    if "스킵" in dl_src or "실패" in dl_src or "데이터없음" in dl_dir:
        dl_score = int(w_dl * 0.38)
    else:
        if dl_raw >= 70:    base = 35
        elif dl_raw >= 50:  base = 27
        elif dl_raw >= 30:  base = 18
        elif dl_raw >= 10:  base = 10
        else:               base = 4
        adj = 5 if "상승" in dl_dir else (-5 if "하락" in dl_dir else 0)
        raw = max(0, min(40, base + adj))
        dl_score = max(0, min(w_dl, round(raw * w_dl / 40)))

    # ── Blog 경쟁도 ──
    raw_bl = blog.get("competition_score", 15)
    blog_total = blog.get("total_results")
    if blog_total is None:
        bl_score = int(w_bl * 0.50)
    else:
        bl_score = max(0, min(w_bl, round(raw_bl * w_bl / 30)))

    # ── 상업 의도 ──
    hits = [w for w in COMMERCIAL_WORDS if w in keyword]
    if len(hits) >= 2:
        com_score = w_co
    elif len(hits) == 1:
        com_score = round(w_co * 0.75)
    else:
        com_score = round(w_co * 0.20)

    # ── Google Trends ──
    gt_raw = gt.get("trend_score", 0)
    gt_dir = gt.get("trend_direction", "")
    gt_src = gt.get("source", "")
    if "실패" in gt_src or "데이터없음" in gt_dir or "스킵" in gt_dir or gt_src == "skipped":
        gt_score = int(w_gt * 0.50)
    else:
        if gt_raw >= 70:   raw_gt = 10
        elif gt_raw >= 40: raw_gt = 7
        elif gt_raw >= 20: raw_gt = 4
        else:              raw_gt = 2
        if "상승" in gt_dir:
            raw_gt = min(10, raw_gt + 1)
        gt_score = max(0, min(w_gt, round(raw_gt * w_gt / 10)))

    total = int(dl_score + bl_score + com_score + gt_score)
    return {
        "total_score": total,
        "dl_score": dl_score, "bl_score": bl_score,
        "com_score": com_score, "gt_score": gt_score,
        "weights": dict(weights),
        "commercial_hits": hits,
    }


def _to_evaluation(keyword: str, dl: dict, blog: dict, gt: dict, scored: dict, profile: str) -> Evaluation:
    """기존 osmu_kr.Evaluation 모델로 변환 — 양호한 후방 호환성 유지."""
    total = scored["total_score"]
    blog_total = blog.get("total_results")
    blog_label = blog.get("competition_label", "")

    # 경쟁도 → 기존 enum 매핑(낮음/중간/높음)
    if blog_total is None:
        comp_kr = "낮음"
    elif blog_total < BLOG_COMP["low"]:
        comp_kr = "낮음"
    elif blog_total < BLOG_COMP["medium"]:
        comp_kr = "중간"
    else:
        comp_kr = "높음"

    # search_volume — DataLab 상대 점수를 절대 검색량 추정으로 변환(매우 거친 추정)
    dl_raw = float(dl.get("trend_score", 0) or 0)
    sv_estimate = int(round(dl_raw * 300))  # 0~30,000 사이로 매핑

    # commercial_intent: hits 0~5 → 0.2 ~ 1.0
    n_hits = len(scored.get("commercial_hits", []))
    commercial_intent = min(1.0, 0.2 + n_hits * 0.20)

    return Evaluation(
        search_volume=sv_estimate,
        competition=comp_kr,
        cpc=0.0,                  # naver_golden 평가기는 CPC 미수집 — 0
        commercial_intent=round(commercial_intent, 3),
        score=float(total),
        raw={
            "evaluator": "naver_golden",
            "profile": profile,
            "datalab": dl,
            "blog": blog,
            "google_trends": gt,
            "components": {
                "datalab": scored["dl_score"],
                "blog": scored["bl_score"],
                "commercial": scored["com_score"],
                "gtrends": scored["gt_score"],
            },
            "weights": scored["weights"],
            "commercial_hits": scored.get("commercial_hits", []),
        },
    )


class NaverGoldenEvaluator(BaseEvaluator):
    name = "naver_golden"

    def __init__(
        self,
        naver_client_id: Optional[str] = None,
        naver_client_secret: Optional[str] = None,
        datalab_client_id: Optional[str] = None,
        datalab_client_secret: Optional[str] = None,
        enable_google_trends: bool = True,
        request_delay_sec: float = 0.4,
    ):
        # 자격증명 — DataLab 키는 비어있으면 일반 키 재사용
        self.naver_id = naver_client_id or os.getenv("NAVER_CLIENT_ID", "")
        self.naver_secret = naver_client_secret or os.getenv("NAVER_CLIENT_SECRET", "")
        self.datalab_id = datalab_client_id or os.getenv("NAVER_DATALAB_CLIENT_ID", "") or self.naver_id
        self.datalab_secret = datalab_client_secret or os.getenv("NAVER_DATALAB_CLIENT_SECRET", "") or self.naver_secret
        self.enable_trends = enable_google_trends
        self.delay = request_delay_sec
        self._fallback = HeuristicEvaluator()
        self._gt_call_count = 0  # rate-limit 보호용

    @property
    def has_naver_credentials(self) -> bool:
        return bool(self.naver_id and self.naver_secret)

    # ── BaseEvaluator 인터페이스 ──
    def evaluate(self, keyword: str, *, seed: str = "") -> Evaluation:
        return self._evaluate_with_profile(keyword, weights=DEFAULT_WEIGHTS,
                                            profile="일반", seed=seed)

    def evaluate_longtail(self, keyword: str, *, seed: str = "") -> Evaluation:
        """알케미 변형 등 롱테일 키워드를 더 관대하게 평가."""
        return self._evaluate_with_profile(keyword, weights=LONGTAIL_WEIGHTS,
                                            profile="롱테일", seed=seed)

    # ── 내부 ─────────────────────────────────────────
    def _evaluate_with_profile(self, keyword: str, *, weights: dict,
                                profile: str, seed: str) -> Evaluation:
        kw = (keyword or "").strip()
        if not kw:
            return Evaluation()

        # 자격증명이 없으면 휴리스틱으로 우아하게 폴백
        if not self.has_naver_credentials:
            ev = self._fallback.evaluate(kw, seed=seed)
            ev.raw = {**ev.raw, "evaluator": "naver_golden(fallback→heuristic)",
                      "reason": "NAVER_CLIENT_ID/SECRET 미설정"}
            return ev

        dl = _fetch_datalab(kw, self.datalab_id, self.datalab_secret)
        if self.delay:
            time.sleep(self.delay)
        blog = _fetch_blog(kw, self.naver_id, self.naver_secret)
        if self.delay:
            time.sleep(self.delay)

        # Google Trends 는 호출 횟수가 누적되면 429 위험 — 처음 N개만
        gt_enabled = self.enable_trends and self._gt_call_count < 5
        gt = _fetch_trends(kw, enabled=gt_enabled)
        if gt_enabled and "skipped" not in gt.get("source", ""):
            self._gt_call_count += 1

        scored = _score(kw, dl, blog, gt, weights)
        return _to_evaluation(kw, dl, blog, gt, scored, profile=profile)


# ── 등급/약점 헬퍼 (researcher 측에서 사용) ───────────
def grade_of(score: float) -> str:
    if score >= 80: return "황금"
    if score >= 60: return "좋은"
    if score >= 40: return "보통"
    return "미달"


def diagnose_weakness(ev: Evaluation) -> list[str]:
    """Evaluation.raw['components'] 에서 약점 추출. naver_golden 외 평가기는 보수적 추정."""
    raw = ev.raw or {}
    comp = raw.get("components") or {}
    weights = raw.get("weights") or {}

    weak = []
    if comp and weights:
        if (comp.get("commercial", 0) / max(1, weights.get("commercial", 20))) < 0.50:
            weak.append("상업의도_부족")
        if (comp.get("blog", 0) / max(1, weights.get("blog_comp", 30))) < 0.40:
            weak.append("경쟁도_높음")
        if (comp.get("datalab", 0) / max(1, weights.get("datalab", 40))) < 0.40:
            weak.append("트렌드_낮음")
    else:
        # 다른 평가기 결과 — 점수만 보고 추정
        if ev.commercial_intent < 0.5:
            weak.append("상업의도_부족")
        if ev.competition in ("중간", "높음"):
            weak.append("경쟁도_높음")
    return weak or ["상업의도_부족", "경쟁도_높음"]
