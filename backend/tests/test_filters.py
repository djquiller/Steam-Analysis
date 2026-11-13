"""全局筛选参数：解析、校验，以及聚合表 / 游戏粒度表两种 WHERE 规则。"""

import pytest
from conftest import assert_bad_param, ok_data
from factories import top_seller_row, yearly_rows

from app import tables as T
from app.errors import ApiError
from app.services.filters import Filters, parse_price_buckets

URL = "/api/v1/trend/yearly"


def test_parse_price_buckets_dedupes_and_orders():
    assert parse_price_buckets("ge60, free,free ,lt10") == ("free", "lt10", "ge60")
    assert parse_price_buckets(None) == ()
    assert parse_price_buckets("  ") == ()


def test_parse_price_buckets_rejects_unknown():
    with pytest.raises(ApiError) as e:
        parse_price_buckets("free,cheap")
    assert e.value.code == 40001 and "cheap" in e.value.msg


def test_agg_where_uses_all_row_without_genre(client, seed):
    seed(T.ads_yearly_release, yearly_rows())
    # 不选类型：只读 __ALL__ 行，2024 = 30 + 5
    data = ok_data(client.get(URL))
    assert [(d["year"], d["game_cnt"]) for d in data] == [(2023, 30), (2024, 35)]


def test_agg_where_uses_genre_rows_with_genre(client, seed):
    seed(T.ads_yearly_release, yearly_rows())
    data = ok_data(client.get(URL, params={"genre": "Action"}))
    assert [(d["year"], d["game_cnt"]) for d in data] == [(2023, 8), (2024, 3)]


def test_year_and_price_filters_combine(client, seed):
    seed(T.ads_yearly_release, yearly_rows())
    data = ok_data(client.get(URL, params={"year_start": 2024, "year_end": 2024, "price_bucket": "10_30"}))
    assert data == [{"year": 2024, "game_cnt": 5, "price_sum": 100.0, "avg_price_usd": 20.0}]


def test_game_where_joins_genre_only_when_selected(client, seed):
    seed(T.ads_yearly_release, yearly_rows())
    seed(T.ads_top_sellers, [top_seller_row(1, owners_mid=900), top_seller_row(2, owners_mid=800)])
    seed(T.dwd_game_genre, [{"appid": 2, "genre": "RPG"}])
    url = "/api/v1/rank/top-sellers"
    assert [d["appid"] for d in ok_data(client.get(url))] == [1, 2]
    assert [d["appid"] for d in ok_data(client.get(url, params={"genre": "RPG"}))] == [2]


@pytest.mark.parametrize("params", [
    {"genre": "NotAGenre"},
    {"genre": "__ALL__"},          # 保留值不是合法的筛选取值
    {"price_bucket": "cheap"},
    {"year_start": 2025, "year_end": 2020},
    {"year_start": "abc"},
    {"year_end": 1800},
])
def test_invalid_filters_return_40001(client, seed, params):
    seed(T.ads_yearly_release, yearly_rows())
    assert_bad_param(client.get(URL, params=params))


def test_filters_dataclass_defaults():
    f = Filters()
    assert f.genre is None and f.price_buckets == ()
