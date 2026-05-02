"""기본 동작 검증 테스트 — pytest 없이도 python -m tests.test_basic 으로 실행 가능."""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "src"))

from osmu_kr import Config, KeywordResearcher  # noqa: E402
from osmu_kr.evaluator import HeuristicEvaluator  # noqa: E402
from osmu_kr.researcher.alchemist import transmute  # noqa: E402
from osmu_kr.researcher.expander import expand  # noqa: E402


def fresh_researcher() -> KeywordResearcher:
    tmp = tempfile.mkdtemp(prefix="osmu_kr_test_")
    os.environ["OSMU_LOCAL_DATA_DIR"] = tmp
    os.environ["OSMU_STORAGE_BACKEND"] = "local"
    os.environ["OSMU_GOLDEN_THRESHOLD"] = "65"
    os.environ["OSMU_MEDIUM_LOWER"] = "45"
    os.environ["OSMU_MEDIUM_UPPER"] = "65"
    os.environ["OSMU_POOL_MAX_SIZE"] = "100"
    return KeywordResearcher(Config())


def test_evaluator_deterministic():
    e = HeuristicEvaluator()
    a = e.evaluate("AI ETF 추천 2025")
    b = e.evaluate("AI ETF 추천 2025")
    assert a.score == b.score
    assert 0 <= a.score <= 100


def test_expander_includes_seed_and_dedups():
    out = expand("다이어트", limit=10)
    assert len(out) == 10
    assert "다이어트" in out
    assert len(set(out)) == len(out)


def test_alchemy_produces_distinct_variants():
    out = transmute("다이어트", max_variants=3)
    assert len(out) == 3
    for v in out:
        assert "다이어트" in v
        assert v != "다이어트"


def test_run_seed_creates_pool_items():
    rs = fresh_researcher()
    rep = rs.run_seed("AI ETF")
    pool = rs.storage.list_pool()
    assert len(pool) >= 1
    assert rep.expanded > 0
    # 모두 'AI ETF' seed에 묶여 있어야 함
    assert all(it.seed_keyword == "AI ETF" for it in pool)


def test_select_records_content_and_removes_from_pool():
    rs = fresh_researcher()
    rs.run_seed("AI ETF")
    pool_before = rs.storage.list_pool()
    pick = pool_before[0]
    rs.select_for_content(pick.keyword_id, title_final="t")
    pool_after = rs.storage.list_pool()
    assert pick.keyword_id not in {it.keyword_id for it in pool_after}
    contents = rs.storage.list_content()
    assert any(r.keyword_id == pick.keyword_id for r in contents)


def test_seed_cooldown_blocks_same_seed():
    rs = fresh_researcher()
    os.environ["OSMU_SEED_COOLDOWN_DAYS"] = "7"
    rs = fresh_researcher()  # 새 cfg 적용
    rs.run_seed("다이어트")
    pool = [it for it in rs.storage.list_pool() if it.seed_keyword == "다이어트"]
    assert len(pool) >= 2, "테스트엔 다이어트 풀에 최소 2개 필요"
    rs.select_for_content(pool[0].keyword_id, title_final="t")
    try:
        rs.select_for_content(pool[1].keyword_id, title_final="t2")
    except PermissionError:
        return  # 기대 동작
    raise AssertionError("동일 seed cooldown이 적용되지 않음")


def test_prune_removes_expired():
    from datetime import timedelta
    from osmu_kr.models import to_iso, now_utc

    rs = fresh_researcher()
    os.environ["OSMU_REVIVAL_DAYS"] = "0.1"
    rs = fresh_researcher()
    rs.run_seed("AI ETF")

    # 모든 항목을 1일 과거로 만들어 만료 처리
    items = rs.storage.list_pool()
    past = now_utc() - timedelta(days=1)
    for it in items:
        it.updated_at = to_iso(past)
        it.created_at = to_iso(past)
    rs.storage.replace_pool(items)

    pool, report = rs.prune()
    assert report.revaluated == len(items)


def test_xlsx_storage_round_trip():
    """LocalXlsxStorage 가 keyword_pool / content_db 를 정확히 라운드트립한다."""
    import tempfile
    from osmu_kr.storage.xlsx_local import LocalXlsxStorage
    from osmu_kr.models import KeywordPoolItem, ContentRecord

    tmp = tempfile.mkdtemp(prefix="osmu_xlsx_test_")
    sx = LocalXlsxStorage(data_dir=tmp)

    sx.upsert_pool(KeywordPoolItem(
        keyword_id="0001", seed_keyword="다이어트", keyword="다이어트 추천",
        score=82.5, status="golden", search_volume=12000, cpc=750.0, competition="낮음",
    ))
    sx.upsert_pool(KeywordPoolItem(
        keyword_id="0002", seed_keyword="다이어트", keyword="다이어트 비교",
        score=70.0, status="golden",
    ))

    rec = ContentRecord(
        id="001", keyword="다이어트 추천", seed_keyword="다이어트", keyword_id="0001",
        status="대기중",
    )
    sx.append_content(rec)

    # 새로운 인스턴스로 다시 읽기 — 영속성 검증
    sx2 = LocalXlsxStorage(data_dir=tmp)
    pool = sx2.list_pool()
    assert len(pool) == 2
    assert {it.keyword_id for it in pool} == {"0001", "0002"}
    contents = sx2.list_content()
    assert len(contents) == 1
    assert contents[0].keyword == "다이어트 추천"

    # delete + replace_content
    assert sx2.delete_pool("0002") is True
    assert len(sx2.list_pool()) == 1

    sx2.replace_content([])
    assert sx2.list_content() == []


def test_factory_xlsx_format():
    """OSMU_LOCAL_FORMAT=xlsx 일 때 LocalXlsxStorage 가 빌드된다."""
    import os, tempfile
    from osmu_kr.config import Config
    from osmu_kr.storage import build_storage

    tmp = tempfile.mkdtemp(prefix="osmu_factory_xlsx_")
    os.environ["OSMU_STORAGE_BACKEND"] = "local"
    os.environ["OSMU_LOCAL_FORMAT"] = "xlsx"
    os.environ["OSMU_LOCAL_DATA_DIR"] = tmp

    storage = build_storage(Config())
    assert storage.name == "xlsx"

    # csv 로 다시 전환했을 때
    os.environ["OSMU_LOCAL_FORMAT"] = "csv"
    storage2 = build_storage(Config())
    assert storage2.name == "local"


def test_mirror_storage_falls_back_to_local_when_no_credentials():
    """MirrorStorage: Sheets factory 가 실패해도 로컬 단독 동작."""
    import tempfile
    from osmu_kr.storage.csv_local import LocalCsvStorage
    from osmu_kr.storage.mirror import MirrorStorage
    from osmu_kr.models import KeywordPoolItem

    tmp = tempfile.mkdtemp(prefix="osmu_mirror_test_")
    local = LocalCsvStorage(data_dir=tmp)

    def factory_fail():
        raise RuntimeError("no credentials")

    mirror = MirrorStorage(local=local, sheets_factory=factory_fail)

    item = KeywordPoolItem(
        keyword_id="0001", seed_keyword="테스트", keyword="테스트 키워드",
        score=80.0, status="golden",
    )
    mirror.upsert_pool(item)

    # 로컬에는 정상 저장됐어야 함
    assert any(it.keyword_id == "0001" for it in mirror.list_pool())

    # Sheets 가 실패했으므로 보류 카운트가 1 이상
    status = mirror.status()
    assert status.pending_writes >= 1
    assert status.sheets_enabled is False


def test_mirror_factory_via_config():
    """OSMU_STORAGE_BACKEND=mirror 일 때 MirrorStorage 가 빌드되는지."""
    import os, tempfile
    from osmu_kr.config import Config
    from osmu_kr.storage import build_storage

    tmp = tempfile.mkdtemp(prefix="osmu_factory_test_")
    os.environ["OSMU_STORAGE_BACKEND"] = "mirror"
    os.environ["OSMU_LOCAL_DATA_DIR"] = tmp
    os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
    os.environ.pop("OSMU_SHEET_ID", None)

    storage = build_storage(Config())
    assert storage.name == "mirror"
    # 자격증명이 없어도 인스턴스가 생성되며 (지연 초기화), 로컬 부분만 동작
    storage.list_pool()  # 예외 없이 호출 가능


TESTS = [
    test_evaluator_deterministic,
    test_expander_includes_seed_and_dedups,
    test_alchemy_produces_distinct_variants,
    test_run_seed_creates_pool_items,
    test_select_records_content_and_removes_from_pool,
    test_seed_cooldown_blocks_same_seed,
    test_prune_removes_expired,
    test_xlsx_storage_round_trip,
    test_factory_xlsx_format,
    test_mirror_storage_falls_back_to_local_when_no_credentials,
    test_mirror_factory_via_config,
]


def main() -> int:
    failed = 0
    for fn in TESTS:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"  FAIL  {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\nresult: {len(TESTS) - failed}/{len(TESTS)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
