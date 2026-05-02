"""커맨드라인 인터페이스.

예시:
    osmu-kr seed --seed "다이어트"
    osmu-kr check --keyword "AI ETF 추천 2025"
    osmu-kr recommend --top 5
    osmu-kr select --id 0001 --title "..."
    osmu-kr prune
    osmu-kr show
"""
from __future__ import annotations

import argparse
import json
import logging
import sys

from .config import Config
from .researcher import KeywordResearcher


def _setup_logging(verbose: bool):
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def _print_pool(researcher: KeywordResearcher):
    items = researcher.storage.list_pool()
    print(f"\n[keyword_pool] {len(items)} item(s)")
    for it in sorted(items, key=lambda x: x.score, reverse=True):
        print(
            f"  - {it.keyword_id} | seed='{it.seed_keyword}' | '{it.keyword}' "
            f"| score={it.score} | sv={it.search_volume} comp={it.competition} cpc={it.cpc} "
            f"| status={it.status}"
        )


def _print_content(researcher: KeywordResearcher):
    items = researcher.storage.list_content()
    print(f"\n[content_db] {len(items)} record(s)")
    for r in items:
        print(
            f"  - id={r.id} keyword='{r.keyword}' seed='{r.seed_keyword}' "
            f"status={r.status} created={r.created_at}"
        )


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="osmu-kr")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    s_seed = sub.add_parser("seed", help="seed → 후보 → pool 저장")
    s_seed.add_argument("--seed", required=True)
    s_seed.add_argument("--limit", type=int, default=10)

    s_check = sub.add_parser("check", help="사용자 직접 입력 키워드 평가")
    s_check.add_argument("--keyword", required=True)
    s_check.add_argument("--seed", default=None)

    s_rec = sub.add_parser("recommend", help="pool에서 추천")
    s_rec.add_argument("--top", type=int, default=5)

    s_sel = sub.add_parser("select", help="pool 항목을 content_db로 이동")
    s_sel.add_argument("--id", required=True)
    s_sel.add_argument("--title", default="")
    s_sel.add_argument("--source", default="")

    sub.add_parser("prune", help="POOL_MAX_SIZE / REVIVAL_DAYS 정리")
    sub.add_parser("show", help="현재 pool / content 보기")
    sub.add_parser("config", help="현재 설정 출력")

    args = p.parse_args(argv)
    _setup_logging(args.verbose)

    cfg = Config()
    researcher = KeywordResearcher(cfg)

    if args.cmd == "config":
        print(cfg.summary())
        return 0

    if args.cmd == "seed":
        rep = researcher.run_seed(args.seed, expand_limit=args.limit)
        print(rep.summary())
        _print_pool(researcher)
        return 0

    if args.cmd == "check":
        item = researcher.check_keyword(args.keyword, seed=args.seed)
        print(json.dumps({
            "keyword_id": item.keyword_id,
            "keyword": item.keyword,
            "score": item.score,
            "status": item.status,
        }, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "recommend":
        items = researcher.recommend(top_n=args.top)
        print(f"\n[recommended] {len(items)} item(s)")
        for it in items:
            print(f"  ★ {it.keyword_id} | '{it.keyword}' | score={it.score} | seed='{it.seed_keyword}'")
        return 0

    if args.cmd == "select":
        rec = researcher.select_for_content(
            args.id, title_final=args.title, original_source=args.source
        )
        print(f"created content: id={rec.id} keyword='{rec.keyword}' seed='{rec.seed_keyword}'")
        return 0

    if args.cmd == "prune":
        pool, report = researcher.prune()
        print(report.summary())
        print(f"final pool size = {len(pool)}")
        return 0

    if args.cmd == "show":
        print(cfg.summary())
        _print_pool(researcher)
        _print_content(researcher)
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
