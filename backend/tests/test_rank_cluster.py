"""/rank/top-sellers、/rank/online-live、/cluster/games。"""

from datetime import datetime

from conftest import assert_bad_param, ok_data
from factories import UTC_NOON, cluster_row, top_seller_row

from app import tables as T

TOP = "/api/v1/rank/top-sellers"


def _sellers(seed):
    seed(T.ads_top_sellers, [
        top_seller_row(10, owners_mid=5000, review_cnt=100, positive_cnt=50),
        top_seller_row(11, owners_mid=5000, review_cnt=900, positive_cnt=810, ccu_latest=300, ccu_at=UTC_NOON),
        top_seller_row(12, owners_mid=None, review_cnt=5, positive_cnt=5, ccu_latest=900, ccu_at=UTC_NOON),
        top_seller_row(13, owners_mid=7000, review_cnt=9, positive_cnt=9, release_year=2020, price_bucket="free",
                       price_usd=0),
    ])


def test_top_sellers_by_owners(client, seed):
    _sellers(seed)
    data = ok_data(client.get(TOP))
    # owners_mid 降序 → review_cnt 降序 → appid；owners_mid 为空的排最后
    assert [d["appid"] for d in data] == [13, 11, 10, 12]
    assert [d["rank"] for d in data] == [1, 2, 3, 4]
    first = data[0]
    assert first["positive_rate"] is None  # 评论数 < 10 不展示好评率
    assert first["price_usd"] == 0.0 and first["ccu_at"] is None
    assert data[1]["positive_rate"] == 0.9 and data[1]["ccu_at"] == "2026-11-12T12:00:00Z"


def test_top_sellers_by_ccu_and_limit(client, seed):
    _sellers(seed)
    data = ok_data(client.get(TOP, params={"metric": "ccu", "limit": 1}))
    assert [(d["appid"], d["ccu_latest"]) for d in data] == [(12, 900)]
    data = ok_data(client.get(TOP, params={"metric": "ccu"}))
    assert [d["appid"] for d in data] == [12, 11]  # 没有在线人数的不返回


def test_top_sellers_filters(client, seed):
    _sellers(seed)
    data = ok_data(client.get(TOP, params={"year_end": 2020, "price_bucket": "free,ge60"}))
    assert [d["appid"] for d in data] == [13]


def test_top_sellers_empty(client):
    assert ok_data(client.get(TOP)) == []
    assert ok_data(client.get(TOP, params={"metric": "ccu"})) == []


def test_top_sellers_invalid(client):
    assert_bad_param(client.get(TOP, params={"metric": "revenue"}))
    assert_bad_param(client.get(TOP, params={"limit": 0}))
    assert_bad_param(client.get(TOP, params={"limit": 51}))


def test_online_live(client, seed):
    prev = datetime(2026, 11, 12, 11, 0)
    seed(T.ads_ccu_latest, [
        {"appid": 1, "name": "A", "player_count": 100, "player_count_prev": 90, "snapshot_at": UTC_NOON},
        {"appid": 2, "name": "B", "player_count": 300, "player_count_prev": None, "snapshot_at": UTC_NOON},
        {"appid": 3, "name": "C", "player_count": 200, "player_count_prev": 250, "snapshot_at": prev},
    ])
    data = ok_data(client.get("/api/v1/rank/online-live", params={"limit": 2}))
    assert data == {
        "snapshot_at": "2026-11-12T12:00:00Z",
        "items": [
            {"rank": 1, "appid": 2, "name": "B", "player_count": 300, "player_count_prev": None},
            {"rank": 2, "appid": 3, "name": "C", "player_count": 200, "player_count_prev": 250},
        ],
    }


def test_online_live_empty(client):
    assert ok_data(client.get("/api/v1/rank/online-live")) == {"snapshot_at": None, "items": []}


def test_online_live_invalid(client):
    assert_bad_param(client.get("/api/v1/rank/online-live", params={"limit": 101}))


CLUSTER = "/api/v1/cluster/games"


def test_cluster_games(client, seed):
    rows = [cluster_row(i, i % 2, sample_key=1000 - i) for i in range(1, 151)]
    rows.append(cluster_row(999, 1, release_year=2010, sample_key=0))
    seed(T.ads_game_cluster, rows)
    data = ok_data(client.get(CLUSTER, params={"limit": 100}))
    assert data["total"] == 151
    assert data["clusters"] == [
        {"cluster_id": 0, "cluster_label": "簇0", "game_cnt": 75},
        {"cluster_id": 1, "cluster_label": "簇1", "game_cnt": 76},
    ]
    # limit 只截断 points，按 sample_key 升序取
    assert len(data["points"]) == 100
    assert data["points"][0]["appid"] == 999 and data["points"][1]["appid"] == 150

    filtered = ok_data(client.get(CLUSTER, params={"year_start": 2024}))
    assert filtered["total"] == 150 and len(filtered["points"]) == 150


def test_cluster_games_genre_filter(client, seed):
    seed(T.ads_yearly_release, [dict(release_year=2024, genre="RPG", price_bucket="lt10", game_cnt=1, price_sum=1)])
    seed(T.ads_game_cluster, [cluster_row(1, 0), cluster_row(2, 1)])
    seed(T.dwd_game_genre, [{"appid": 2, "genre": "RPG"}])
    data = ok_data(client.get(CLUSTER, params={"genre": "RPG"}))
    assert data["total"] == 1 and [p["appid"] for p in data["points"]] == [2]


def test_cluster_games_empty(client):
    assert ok_data(client.get(CLUSTER)) == {"total": 0, "clusters": [], "points": []}


def test_cluster_games_invalid(client):
    assert_bad_param(client.get(CLUSTER, params={"limit": 99}))
    assert_bad_param(client.get(CLUSTER, params={"limit": 10001}))
