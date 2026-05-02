"""시연 시나리오 2
==================
description의 두 번째 시연 기준:
    "POOL_MAX_SIZE를 5로 설정하고, REVIVAL_DAYS를 0.1로 설정하여
     약 2.4시간 기준으로 테스트를 수행한다.
     이를 통해 키워드가 자동으로 재평가되거나 삭제되는지 확인한다."

시간 기다리기를 데모에 강요할 수 없으므로,
created_at/updated_at 을 인위적으로 과거로 옮겨서
REVIVAL_DAYS 초과 상태를 만들고 prune() 동작을 검증한다.

또한 동일 seed 기반 콘텐츠 간격 제어(cooldown) 동작도 같이 확인한다.

실행:
    cd osmu_keyword_researcher
    PYTHONPATH=src python demos/scenario_2.py
"""
from __future__ import annotations

import os
import shutil
import sys
from datetime import timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

from osmu_kr import Config, KeywordResearcher  # noqa: E402
from osmu_kr.models import (  # noqa: E402
    ContentRecord,
    from_iso,
    now_utc,
    to_iso,
)


def reset_local_data(data_dir: str = "./data/scenario_2"):
    """기존 CSV가 있으면 truncate(=헤더만 남김). rmtree는 일부 마운트에서
    퍼미션 오류가 나므로 회피한다."""
    os.makedirs(data_dir, exist_ok=True)
    for fname in ("keyword_pool.csv", "content_db.csv"):
        path = os.path.join(data_dir, fname)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("")  # 빈 파일 → CSV 모듈이 헤더 자동 재생성
        except OSError:
            pass
    return data_dir


def age_pool(rs: KeywordResearcher, days: float):
    """모든 풀 항목의 updated_at을 days만큼 과거로 만든다."""
    items = rs.storage.list_pool()
    past = now_utc() - timedelta(days=days)
    for it in items:
        it.updated_at = to_iso(past)
        it.created_at = to_iso(past)
    rs.storage.replace_pool(items)


def main():
    print("=" * 70)
    print("시연 시나리오 ②  POOL_MAX_SIZE / REVIVAL_DAYS 관리")
    print("=" * 70)

    data_dir = reset_local_data()

    # description의 시연 조건 그대로 적용
    os.environ["OSMU_LOCAL_DATA_DIR"] = data_dir
    os.environ["OSMU_STORAGE_BACKEND"] = "local"
    os.environ["OSMU_POOL_MAX_SIZE"] = "5"
    os.environ["OSMU_REVIVAL_DAYS"] = "0.1"
    os.environ["OSMU_SEED_COOLDOWN_DAYS"] = "0.1"  # 시연 편의
    os.environ["OSMU_GOLDEN_THRESHOLD"] = "65"
    os.environ["OSMU_MEDIUM_LOWER"] = "45"
    os.environ["OSMU_MEDIUM_UPPER"] = "65"

    cfg = Config()
    print("\nconfig:", cfg.summary())

    rs = KeywordResearcher(cfg)

    # ── (1) seed 두 개 입력 → 풀이 5를 초과하는지 확인 ──────────
    print("\n[1] 두 seed 실행 → 풀이 자동으로 POOL_MAX_SIZE=5로 정리되는지 확인")
    for seed in ["다이어트", "AI ETF", "챗GPT 활용법"]:
        rep = rs.run_seed(seed)
        print(f"   - run_seed('{seed}') → {rep.summary()}")
    pool = rs.storage.list_pool()
    print(f"   ▶ 현재 pool 크기 = {len(pool)} (기대: ≤5)")
    assert len(pool) <= cfg.pool_max_size, "POOL_MAX_SIZE 정책 위반!"

    print("\n   현재 pool:")
    for it in sorted(pool, key=lambda x: x.score, reverse=True):
        print(f"     · {it.keyword_id} '{it.keyword}' score={it.score} updated_at={it.updated_at}")

    # ── (2) REVIVAL_DAYS=0.1 — 모든 항목을 0.2일 과거로 만든 뒤 prune() ─────
    print("\n[2] 모든 풀 항목의 updated_at을 0.2일 과거로 만든 뒤 prune() 호출")
    age_pool(rs, days=0.2)
    pool, report = rs.prune()
    print(f"   ▶ prune 결과: {report.summary()}")
    print(f"   ▶ prune 후 pool 크기 = {len(pool)}")
    print("   prune 후 pool:")
    for it in sorted(pool, key=lambda x: x.score, reverse=True):
        print(
            f"     · {it.keyword_id} '{it.keyword}' score={it.score} "
            f"status={it.status} updated_at={it.updated_at}"
        )

    # ── (2-b) 재평가 후 삭제 경로 검증 ─────────────────────────
    print("\n[2-b] 의도적으로 점수가 낮은 키워드를 풀에 끼워 넣고 prune → 삭제(expire) 확인")
    from osmu_kr.models import KeywordPoolItem, STATUS_MEDIUM

    # 풀에 medium 키워드를 직접 1개 추가 (REVIVAL 초과 상태)
    fake_medium = KeywordPoolItem(
        keyword_id="9999",
        seed_keyword="저품질샘플",
        keyword="저품질샘플",       # 짧은 단어 → 휴리스틱상 점수 낮게 산정
        score=50.0,
        status=STATUS_MEDIUM,
        source="manual",
        note="prune 데모용 medium 샘플",
    )
    rs.storage.upsert_pool(fake_medium)
    age_pool(rs, days=0.2)  # 다시 만료 직전으로 만든다
    pool, report = rs.prune()
    print(f"   ▶ prune 결과: {report.summary()}")
    survived_ids = {it.keyword_id for it in pool}
    print(
        "   ▶ '9999' 만료 처리 결과:",
        "EXPIRED ✅" if "9999" not in survived_ids else "남아있음(점수 재평가 결과)",
    )

    # ── (3) seed 간격 제어 검증 ──────────────────────────────
    print("\n[3] 동일 seed 기반 콘텐츠 간격 제어 검증")
    print("    (a) 추천된 키워드를 select_for_content() → content_db 기록")
    rec = rs.recommend(top_n=3)
    if not rec:
        print("    pool이 비어 추천 항목 없음. seed 다시 실행 후 재시도.")
        rs.run_seed("재테크")
        rec = rs.recommend(top_n=3)
    pick = rec[0]
    print(f"    선택: {pick.keyword_id} '{pick.keyword}' seed='{pick.seed_keyword}'")
    rs.select_for_content(pick.keyword_id, title_final="시연용 제목")

    print("    (b) 동일 seed의 다른 키워드를 즉시 선택 시도 (차단 기대)")
    # 동일 seed로 새 후보 풀 채우기
    rs.run_seed(pick.seed_keyword)
    same_seed_items = [it for it in rs.storage.list_pool() if it.seed_keyword == pick.seed_keyword]
    if not same_seed_items:
        print("    동일 seed 키워드가 풀에 없음 — 강제 추가")
        rs.check_keyword(f"{pick.seed_keyword} 비교", seed=pick.seed_keyword)
        same_seed_items = [it for it in rs.storage.list_pool() if it.seed_keyword == pick.seed_keyword]

    target = same_seed_items[0]
    try:
        rs.select_for_content(target.keyword_id, title_final="중복 시도")
        print("    ❌ 차단되지 않았음 — 정책 오류")
    except PermissionError as e:
        print(f"    ✅ 차단됨 (예상대로): {e}")

    print("\n   recommend()도 동일 seed를 후보에서 제외하는지 확인:")
    rec_now = rs.recommend(top_n=10)
    seeds_in_rec = sorted({it.seed_keyword for it in rec_now})
    print(f"     - 추천 후보 seed: {seeds_in_rec}")
    print(f"     - 차단된 seed='{pick.seed_keyword}'가 위 목록에 없는지 확인 → "
          f"{'OK' if pick.seed_keyword not in seeds_in_rec else 'FAIL'}")

    print("\n   content_db 현재 상태:")
    for r in rs.storage.list_content():
        print(f"     · id={r.id} keyword='{r.keyword}' seed='{r.seed_keyword}' status={r.status}")

    print(f"\n로컬 데이터 위치: {os.path.abspath(data_dir)}")


if __name__ == "__main__":
    main()
