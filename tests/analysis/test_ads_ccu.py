"""在线人数汇总的两条口径：取哪一轮当"最新"、24 小时峰值取哪一轮。不连数据库。"""
from __future__ import annotations

from datetime import datetime, timedelta

from analysis.build_ads_ccu import pick_latest_complete, pick_peak

H = timedelta(hours=1)
T0 = datetime(2026, 11, 13, 12, 0)


def test_latest_skips_round_in_progress():
    # 13:00 这一轮只采了一半（手动运行时正赶上采集），应退回到 12:00
    rounds = [(T0, 708), (T0 + H, 350)]
    assert pick_latest_complete(rounds, watchlist_size=708) == T0


def test_latest_accepts_round_with_a_few_failures():
    # 少数 appid 接口返回 404 属于正常，达到名单的 90% 就算完整
    rounds = [(T0, 708), (T0 + H, 640)]
    assert pick_latest_complete(rounds, watchlist_size=708) == T0 + H


def test_latest_none_when_no_complete_round():
    assert pick_latest_complete([], watchlist_size=708) is None
    assert pick_latest_complete([(T0, 10)], watchlist_size=708) is None


def test_latest_with_empty_watchlist_still_needs_one_row():
    assert pick_latest_complete([(T0, 1)], watchlist_size=0) == T0


def test_peak_window_ends_at_latest_round_and_spans_24h():
    totals = [
        (T0 - 24 * H, 9_999_999),   # 正好 24 小时前：不在窗口内（左开）
        (T0 - 23 * H, 5_000_000),
        (T0 - 3 * H, 6_500_000),
        (T0, 6_000_000),
        (T0 + H, 9_000_000),        # 比"最新完整轮"还晚（不完整）：调用方不会传进来，传进来也不算
    ]
    assert pick_peak(totals, latest=T0) == (T0 - 3 * H, 6_500_000)


def test_peak_ties_prefer_later_round():
    totals = [(T0 - 5 * H, 100), (T0 - 2 * H, 100), (T0, 50)]
    assert pick_peak(totals, latest=T0) == (T0 - 2 * H, 100)


def test_peak_none_when_window_empty():
    assert pick_peak([(T0 - 30 * H, 1)], latest=T0) is None
