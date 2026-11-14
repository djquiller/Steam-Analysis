"""评论侧 ads 聚合的两处纯逻辑：时长分箱是否与契约一致、分块是否覆盖全部 appid。不连数据库。"""
from __future__ import annotations

import re
from pathlib import Path

from analysis import build_ads_review as m

SCHEMA = Path(__file__).resolve().parents[2] / "docs" / "schema.md"


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql, args=None):
        pass

    def fetchall(self):
        return self.rows


def test_playtime_bounds_match_schema():
    # docs/schema.md 的分箱表里"下界（分钟）"一行：0, 60, 120, …；第一档下界 0 不需要写进 CASE
    line = next(l for l in SCHEMA.read_text(encoding="utf-8").splitlines() if l.startswith("| 下界（分钟）"))
    bounds = [int(x) for x in re.findall(r"\d+", line)]
    assert bounds[0] == 0
    assert m.PLAYTIME_BOUNDS == bounds[1:]


def test_playtime_case_covers_all_bins_and_missing():
    sql = m.PLAYTIME_BIN
    assert f"IS NULL THEN {m.PLAYTIME_MISSING}" in sql
    for i, b in enumerate(m.PLAYTIME_BOUNDS):
        assert f"< {b} THEN {i}" in sql
    assert sql.endswith(f"ELSE {len(m.PLAYTIME_BOUNDS)} END")


def test_chunks_cover_whole_appid_space_contiguously(monkeypatch):
    monkeypatch.setattr(m, "CHUNK_REVIEWS", 100)
    rows = [(10, 60), (20, 50), (30, 10), (40, 200), (50, 1)]
    chunks = m.plan_chunks(FakeCursor(rows))
    assert chunks[0][0] == 0 and chunks[-1][1] == 2 ** 32
    assert all(a[1] == b[0] for a, b in zip(chunks, chunks[1:]))
    # 累计到 20 时达到 110 ≥ 100 → 在 21 切开；40 单独就 ≥ 100 → 在 41 切开
    assert chunks == [(0, 21), (21, 41), (41, 2 ** 32)]


def test_chunks_single_block_when_small(monkeypatch):
    monkeypatch.setattr(m, "CHUNK_REVIEWS", 10_000)
    assert m.plan_chunks(FakeCursor([(10, 5), (20, 5)])) == [(0, 2 ** 32)]
