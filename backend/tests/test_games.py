"""/games/{appid}、/games/{appid}/reviews-trend、/games/{appid}/price-history。"""

from datetime import date

import pytest
from conftest import assert_bad_param, ok_data
from factories import cluster_row, game_row

from app import tables as T


def test_detail_basic_only(client, seed):
    seed(T.dwd_game, [game_row(730, name="Counter-Strike 2", price_usd=0, price_bucket="free", positive=7,
                               negative=2, on_mac=1)])
    seed(T.dwd_game_genre, [{"appid": 730, "genre": "Free To Play"}, {"appid": 730, "genre": "Action"}])
    data = ok_data(client.get("/api/v1/games/730"))
    assert data["name"] == "Counter-Strike 2"
    assert data["genres"] == ["Action", "Free To Play"]
    assert data["platforms"] == ["windows", "mac", "linux"]
    assert data["release_date"] == "2024-03-01" and data["release_year"] == 2024
    assert data["review_cnt"] == 9 and data["positive_cnt"] == 7
    assert data["positive_rate"] is None  # 评论数 < 10
    # 模型结果表里没有这款游戏：四块都是 null
    assert data["cluster"] is None and data["peers"] is None
    assert data["hot_pred"] is None and data["sentiment"] is None


def test_detail_with_model_results(client, seed):
    seed(T.dwd_game, [game_row(1), game_row(2), game_row(3)])
    seed(T.ads_game_cluster, [
        cluster_row(1, 2, price_usd=10, positive_rate=0.8, owners_mid=1000, avg_playtime_min=100),
        cluster_row(2, 2, price_usd=20, positive_rate=0.9, owners_mid=3001, avg_playtime_min=201),
        cluster_row(3, 0),
    ])
    seed(T.ads_hot_pred, [{"appid": 1, "hot_prob": 0.9312, "hot_pred": 1, "hot_actual": 0, "is_test": 1,
                           "model_name": "hot_rf"}])
    seed(T.ads_review_sentiment, [{"appid": 1, "sample_cnt": 20, "positive_cnt": 17, "method": "model"}])
    data = ok_data(client.get("/api/v1/games/1"))
    assert data["positive_rate"] == 0.9
    assert data["cluster"] == {"cluster_id": 2, "cluster_label": "簇2"}
    assert data["peers"] == {"cluster_id": 2, "cluster_label": "簇2", "game_cnt": 2, "avg_price_usd": 15.0,
                             "avg_positive_rate": 0.85, "avg_owners_mid": 2000, "avg_playtime_min": 150}
    assert data["hot_pred"] == {"hot_prob": 0.9312, "hot_pred": True, "hot_actual": False, "is_test": True,
                                "model_name": "hot_rf"}
    assert data["sentiment"] == {"sample_cnt": 20, "positive_cnt": 17, "positive_ratio": 0.85, "method": "model"}


@pytest.mark.parametrize("suffix", ["", "/reviews-trend", "/price-history"])
def test_unknown_appid_returns_40401(client, suffix):
    r = client.get(f"/api/v1/games/123{suffix}")
    assert r.status_code == 404
    assert r.json() == {"code": 40401, "msg": "游戏不存在：appid=123", "data": None}


@pytest.mark.parametrize("appid", ["0", "-5", "abc"])
def test_invalid_appid(client, appid):
    assert_bad_param(client.get(f"/api/v1/games/{appid}"))


def test_reviews_trend(client, seed):
    seed(T.dwd_game, [game_row(1)])
    seed(T.ads_game_review_trend, [
        {"appid": 1, "month_start": date(2025, 10, 1), "review_cnt": 8, "positive_cnt": 6},
        {"appid": 1, "month_start": date(2025, 9, 1), "review_cnt": 3, "positive_cnt": 1},
        {"appid": 2, "month_start": date(2025, 9, 1), "review_cnt": 5, "positive_cnt": 5},
    ])
    assert ok_data(client.get("/api/v1/games/1/reviews-trend")) == [
        {"month": "2025-09", "review_cnt": 3, "positive_cnt": 1, "positive_rate": 0.3333},
        {"month": "2025-10", "review_cnt": 8, "positive_cnt": 6, "positive_rate": 0.75},
    ]


def test_reviews_trend_empty(client, seed):
    seed(T.dwd_game, [game_row(1)])
    assert ok_data(client.get("/api/v1/games/1/reviews-trend")) == []


def test_price_history(client, seed):
    seed(T.dwd_game, [game_row(1)])
    seed(T.dwd_price_history, [
        {"appid": 1, "snapshot_date": date(2026, 11, 21), "price_usd": 19.49},
        {"appid": 1, "snapshot_date": date(2026, 11, 20), "price_usd": 29.99},
    ])
    assert ok_data(client.get("/api/v1/games/1/price-history")) == [
        {"date": "2026-11-20", "price_usd": 29.99},
        {"date": "2026-11-21", "price_usd": 19.49},
    ]


def test_price_history_empty(client, seed):
    seed(T.dwd_game, [game_row(1)])
    assert ok_data(client.get("/api/v1/games/1/price-history")) == []
