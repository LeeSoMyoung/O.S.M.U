"""시연 시나리오 1
==================
description의 첫 번째 시연 기준:
    "씨앗 키워드를 입력했을 때, 관련 키워드가 생성되고,
     평가를 거쳐 keyword_pool 시트에 자동으로 저장되는 흐름이다.
     이때 키워드 연금술이 적용되어 일부 키워드가 변형되는 과정까지 포함되어야 한다."

실행:
    cd osmu_keyword_researcher
    PYTHONPATH=src python demos/scenario_1.py
"""
from __future__ import annotations

import os
import shutil
import sys

# src 경로 자동 등록
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

from osmu_kr import Config, KeywordResearcher  # noqa: E402


def reset_local_data(data_dir: str = "./data/scenario_1"):
    """기존 CSV가 있으면 truncate. rmtree 회피."""
    os.makedirs(data_dir, exist_ok=True)
    for fname in ("keyword_pool.csv", "content_db.csv"):
        path = os.path.join(data_dir, fname)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("")
        except OSError:
            pass
    return data_dir


def main():
    print("=" * 70)
    print("시연 시나리오 ①  seed → 후보 → 평가 → pool 저장 (+ 연금술)")
    print("=" * 70)

    # 깨끗한 데이터 디렉터리
    data_dir = reset_local_data()
    os.environ["OSMU_LOCAL_DATA_DIR"] = data_dir
    os.environ["OSMU_STORAGE_BACKEND"] = "local"
    # medium 임계를 넓게 잡아 연금술 동작이 충분히 보이도록
    os.environ.setdefault("OSMU_GOLDEN_THRESHOLD", "65")
    os.environ.setdefault("OSMU_MEDIUM_LOWER", "45")
    os.environ.setdefault("OSMU_MEDIUM_UPPER", "65")
    os.environ.setdefault("OSMU_POOL_MAX_SIZE", "50")

    cfg = Config()
    print("\nconfig:", cfg.summary())

    rs = KeywordResearcher(cfg)

    seeds = ["다이어트", "AI ETF", "챗GPT 활용법"]

    for seed in seeds:
        print("\n" + "─" * 60)
        print(f"▶ run_seed('{seed}')")
        rep = rs.run_seed(seed)
        print("  ", rep.summary())
        for it in rep.items:
            tag = "(연금술)" if "alchemy" in it.source else ""
            print(
                f"   · {it.keyword_id} '{it.keyword}' "
                f"[score={it.score} sv={it.search_volume} comp={it.competition} cpc={it.cpc}] {tag}"
            )

    print("\n" + "=" * 70)
    print("최종 keyword_pool")
    print("=" * 70)
    pool = rs.storage.list_pool()
    pool.sort(key=lambda x: x.score, reverse=True)
    for it in pool:
        print(
            f"  ★ {it.keyword_id} seed='{it.seed_keyword}' '{it.keyword}' "
            f"score={it.score:>5} sv={it.search_volume:>6} comp={it.competition} "
            f"cpc={it.cpc:>5} status={it.status} source={it.source}"
        )

    # 추천 결과 (아직 content_db에 사용 이력이 없으므로 score 순)
    print("\n[recommend top 5]")
    for it in rs.recommend(top_n=5):
        print(f"  ★ {it.keyword_id} '{it.keyword}' (score={it.score}, seed='{it.seed_keyword}')")

    # CSV 위치 안내
    print(f"\n로컬 데이터 위치: {os.path.abspath(data_dir)}")
    print("  - keyword_pool.csv")
    print("  - content_db.csv  (이번 단계에선 비어 있음)")


if __name__ == "__main__":
    main()
