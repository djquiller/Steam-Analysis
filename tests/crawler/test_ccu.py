"""在线人数采集：名单生成的确定性、响应解析、单款失败的分类。不连数据库，不访问外网。"""
from __future__ import annotations

import random

import httpx

from crawler.ccu_snapshot import fetch_one, parse_player_count
from crawler.ccu_watchlist import select_watchlist
from crawler.common.http import HttpClient

SECRET = "FAKE-KEY-FOR-UNIT-TESTS-ONLY-XYZ"


def make_games(n: int = 5000, seed: int = 7) -> list[tuple[int, int | None, int | None]]:
    """造一批游戏：owners_mid 只有几个档位（大量并列），peak_ccu 也有并列和 NULL。"""
    rng = random.Random(seed)
    tiers = [10_000, 35_000, 75_000, 150_000, 350_000, 750_000, 1_500_000, 3_500_000]
    games = []
    for appid in rng.sample(range(10, 2_000_000), n):
        peak = rng.choice([None, 0, 0, 1, 5, 5, 50, rng.randint(0, 100_000)])
        games.append((appid, peak, rng.choice(tiers)))
    return games


# ------------------------------------------------------------ 名单生成 ----

def test_watchlist_is_independent_of_input_order():
    games = make_games()
    expected = select_watchlist(games, top_n=500)
    rng = random.Random(1)
    for _ in range(5):
        shuffled = games[:]
        rng.shuffle(shuffled)
        assert select_watchlist(shuffled, top_n=500) == expected


def test_watchlist_is_union_without_duplicates_and_sorted():
    items = select_watchlist(make_games(), top_n=500)
    appids = [it.appid for it in items]
    assert appids == sorted(set(appids))
    assert sum(it.peak_ccu_rank is not None for it in items) == 500
    assert sum(it.owners_rank is not None for it in items) == 500
    assert 500 <= len(items) <= 1000
    assert all(it.peak_ccu_rank is not None or it.owners_rank is not None for it in items)


def test_owners_ties_break_by_peak_ccu_then_appid():
    # 四款同一档：先比 peak_ccu（高的在前），再比 appid（小的在前）
    games = [(40, 10, 1000), (30, 99, 1000), (20, 10, 1000), (10, 5, 1000), (50, 500, 10)]
    ranks = {it.appid: it.owners_rank for it in select_watchlist(games, top_n=3)}
    assert ranks[30] == 1 and ranks[20] == 2 and ranks[40] == 3
    assert ranks.get(10) is None  # 同档但排在第 4，没进前 3（它也没进 peak 榜，所以不在名单里）


def test_peak_ties_break_by_appid_and_null_counts_as_zero():
    games = [(3, 7, 0), (1, 7, 0), (2, 7, 0), (9, None, 0), (8, 0, 0)]
    items = select_watchlist(games, top_n=2)
    assert {it.appid: it.peak_ccu_rank for it in items if it.peak_ccu_rank} == {1: 1, 2: 2}
    # NULL 与 0 等价，按 appid 排：8 在 9 前
    ranks = {it.appid: it.peak_ccu_rank for it in select_watchlist(games, top_n=4)}
    assert ranks[8] == 4 and ranks.get(9) is None


def test_watchlist_smaller_than_top_n():
    assert [it.appid for it in select_watchlist([(5, 1, 1), (4, 2, 2)], top_n=500)] == [4, 5]


# ------------------------------------------------------------ 响应解析 ----

def test_parse_player_count():
    assert parse_player_count({"response": {"player_count": 123, "result": 1}}) == 123
    assert parse_player_count({"response": {"player_count": 0, "result": 1}}) == 0
    assert parse_player_count({"response": {"result": 42}}) is None
    assert parse_player_count({"response": {"player_count": 5, "result": 42}}) is None
    assert parse_player_count({"response": {"player_count": -1, "result": 1}}) is None
    assert parse_player_count({"response": {"player_count": "12", "result": 1}}) is None
    assert parse_player_count({}) is None
    assert parse_player_count([]) is None
    assert parse_player_count(None) is None


# ---------------------------------------------------------- 单款的结果 ----

def client_for(handler) -> HttpClient:
    return HttpClient(transport=httpx.MockTransport(handler), sleep=lambda s: None,
                      max_attempts=2, secrets=[SECRET])


def test_fetch_one_ok():
    client = client_for(lambda req: httpx.Response(200, json={"response": {"player_count": 987, "result": 1}}))
    r = fetch_one(client, SECRET, 730)
    assert (r.appid, r.category, r.player_count, r.http_status, r.error) == (730, "ok", 987, 200, None)
    assert '"player_count"' in r.raw_body


def test_fetch_one_404_is_no_data_and_not_retried():
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(404, json={"response": {"result": 42}})

    r = fetch_one(client_for(handler), SECRET, 12345)
    assert r.category == "no_data" and r.player_count is None and r.http_status == 404
    assert len(calls) == 1


def test_fetch_one_bad_payload():
    r = fetch_one(client_for(lambda req: httpx.Response(200, text="<html>oops</html>")), SECRET, 1)
    assert r.category == "bad_payload" and r.player_count is None and r.raw_body == "<html>oops</html>"


def test_fetch_one_failures_never_raise_and_never_leak_key():
    def boom(req):
        raise httpx.ConnectError(f"failed: {req.url}")

    for handler, category in ((boom, "network"),
                              (lambda req: httpx.Response(403), "http_403"),
                              (lambda req: httpx.Response(500), "http_500")):
        r = fetch_one(client_for(handler), SECRET, 570)
        assert r.category == category and r.player_count is None
        assert r.error and SECRET not in r.error and len(r.error) <= 255
