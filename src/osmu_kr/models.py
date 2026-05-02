"""데이터 모델.

DB 모델 결정 (사용자 확정):
    정규화 + content_db 사용이력 추적

  ┌─────────────────────────┐      ┌────────────────────────────────────┐
  │ keyword_pool (시트)      │      │ content_db (시트, 기획서 §1과 호환) │
  │  keyword_id (PK)        │◀─────│  ... + keyword_id (FK)            │
  │  seed_keyword           │      │      + seed_keyword (denorm)       │
  │  keyword                │      │      + created_at                  │
  │  search_volume          │      └────────────────────────────────────┘
  │  competition            │
  │  cpc                    │   "이 키워드를 마지막으로 쓴 시점"은
  │  commercial_intent      │     keyword_pool에 두지 않고
  │  score                  │     content_db.created_at 으로 조회한다.
  │  status                 │     (멀티 계정 확장성 확보)
  │  created_at             │
  │  updated_at             │
  │  source                 │
  │  note                   │
  └─────────────────────────┘
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional

ISO = "%Y-%m-%dT%H:%M:%S%z"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def to_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime(ISO)


def from_iso(s: str) -> datetime:
    if not s:
        return now_utc()
    # tz 정보가 없는 옛 데이터도 허용
    try:
        return datetime.strptime(s, ISO)
    except ValueError:
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


# 황금 키워드 상태값
STATUS_GOLDEN = "golden"
STATUS_MEDIUM = "medium"
STATUS_REJECTED = "rejected"
STATUS_USED = "used"
STATUS_EXPIRED = "expired"


@dataclass
class Evaluation:
    """평가 모듈의 표준 출력 (모든 Evaluator 공통 인터페이스)."""

    search_volume: int = 0
    competition: str = "낮음"  # 낮음 / 중간 / 높음
    cpc: float = 0.0
    commercial_intent: float = 0.0  # 0~1
    score: float = 0.0  # 0~100 (황금 점수)
    raw: dict = field(default_factory=dict)

    def to_row(self) -> dict:
        return {
            "search_volume": self.search_volume,
            "competition": self.competition,
            "cpc": self.cpc,
            "commercial_intent": round(self.commercial_intent, 3),
            "score": round(self.score, 2),
        }


@dataclass
class KeywordPoolItem:
    keyword_id: str
    seed_keyword: str
    keyword: str
    search_volume: int = 0
    competition: str = "낮음"
    cpc: float = 0.0
    commercial_intent: float = 0.0
    score: float = 0.0
    status: str = STATUS_GOLDEN
    created_at: str = field(default_factory=lambda: to_iso(now_utc()))
    updated_at: str = field(default_factory=lambda: to_iso(now_utc()))
    source: str = "heuristic"
    note: str = ""

    HEADER = [
        "keyword_id",
        "seed_keyword",
        "keyword",
        "search_volume",
        "competition",
        "cpc",
        "commercial_intent",
        "score",
        "status",
        "created_at",
        "updated_at",
        "source",
        "note",
    ]

    def to_row(self) -> list:
        d = asdict(self)
        return [d[k] for k in self.HEADER]

    @classmethod
    def from_row(cls, row: list) -> "KeywordPoolItem":
        # 짧은 행이라도 안전하게 처리
        padded = list(row) + [""] * (len(cls.HEADER) - len(row))
        d = dict(zip(cls.HEADER, padded))
        return cls(
            keyword_id=str(d["keyword_id"]),
            seed_keyword=str(d["seed_keyword"]),
            keyword=str(d["keyword"]),
            search_volume=int(float(d["search_volume"] or 0)),
            competition=str(d["competition"] or "낮음"),
            cpc=float(d["cpc"] or 0),
            commercial_intent=float(d["commercial_intent"] or 0),
            score=float(d["score"] or 0),
            status=str(d["status"] or STATUS_GOLDEN),
            created_at=str(d["created_at"] or to_iso(now_utc())),
            updated_at=str(d["updated_at"] or to_iso(now_utc())),
            source=str(d["source"] or "heuristic"),
            note=str(d["note"] or ""),
        )


@dataclass
class ContentRecord:
    """기획서 §1 content_db 헤더와 호환되는 모델.

    Keyword Researcher 단계에서는 keyword_id / seed_keyword / created_at
    세 컬럼만 적극적으로 사용한다.
    """

    id: str
    keyword: str
    seed_keyword: str = ""
    keyword_id: str = ""
    original_source: str = ""
    status: str = "대기중"
    title_final: str = ""
    platform_url: str = ""
    created_at: str = field(default_factory=lambda: to_iso(now_utc()))
    published_at: str = ""
    raw_content: str = ""
    refined_post: str = ""
    image_urls: str = ""
    error_log: str = ""
    note: str = ""

    HEADER = [
        "id",
        "keyword",
        "seed_keyword",
        "keyword_id",
        "original_source",
        "status",
        "title_final",
        "platform_url",
        "created_at",
        "published_at",
        "raw_content",
        "refined_post",
        "image_urls",
        "error_log",
        "note",
    ]

    def to_row(self) -> list:
        d = asdict(self)
        return [d[k] for k in self.HEADER]

    @classmethod
    def from_row(cls, row: list) -> "ContentRecord":
        padded = list(row) + [""] * (len(cls.HEADER) - len(row))
        d = dict(zip(cls.HEADER, padded))
        return cls(**{k: str(v) if v is not None else "" for k, v in d.items()})
