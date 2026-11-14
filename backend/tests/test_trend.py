"""/trend/yearly、/trend/genres、/trend/price-rating。"""

from conftest import assert_bad_param, ok_data
from factories import yearly_rows

from app import tables as T
from app.services.trend import five_numbers


def test_yearly(client, seed):
    seed(T.ads_yearly_release, yearly_rows())
    data = ok_data(client.get("/api/v1/trend/yearly"))
    assert data == [
        {"year": 2023, "game_cnt": 30, "price_sum": 100.0, "avg_price_usd": 3.33},
        {"year": 2024, "game_cnt": 35, "price_sum": 250.0, "avg_price_usd": 7.14},
    ]


def test_yearly_empty(client, seed):
    seed(T.ads_yearly_release, yearly_rows())
    assert ok_data(client.get("/api/v1/trend/yearly", params={"year_start": 2030})) == []


def test_yearly_invalid(client):
    assert_bad_param(client.get("/api/v1/trend/yearly", params={"price_bucket": "lt5"}))


def _heat(year, genre, bucket, cnt, owners, reviews, pos):
    return dict(release_year=year, genre=genre, price_bucket=bucket, game_cnt=cnt, owners_sum=owners,
                review_cnt=reviews, positive_cnt=pos)


def test_genres_ignores_genre_param(client, seed):
    seed(T.ads_yearly_release, yearly_rows())
    seed(T.ads_genre_heat, [
        _heat(2023, "Action", "lt10", 8, 800, 1000, 900),
        _heat(2024, "Action", "10_30", 3, 300, 0, 0),
        _heat(2024, "RPG", "10_30", 20, 2000, 400, 100),
    ])
    expected = [
        {"genre": "RPG", "game_cnt": 20, "owners_sum": 2000, "review_cnt": 400, "positive_cnt": 100, "positive_rate": 0.25},
        {"genre": "Action", "game_cnt": 11, "owners_sum": 1100, "review_cnt": 1000, "positive_cnt": 900, "positive_rate": 0.9},
    ]
    assert ok_data(client.get("/api/v1/trend/genres")) == expected
    # 传了 genre 照常返回全部类型（树图由前端高亮）
    assert ok_data(client.get("/api/v1/trend/genres", params={"genre": "Action"})) == expected
    only_2024 = ok_data(client.get("/api/v1/trend/genres", params={"year_start": 2024}))
    assert [(d["genre"], d["game_cnt"], d["positive_rate"]) for d in only_2024] == [("RPG", 20, 0.25), ("Action", 3, None)]


def test_genres_empty(client):
    assert ok_data(client.get("/api/v1/trend/genres")) == []


def test_genres_invalid(client):
    assert_bad_param(client.get("/api/v1/trend/genres", params={"year_start": "x"}))


def test_five_numbers_follows_contract():
    # 10 款游戏：分箱 10 有 1 款，50 有 4 款，80 有 4 款，99 有 1 款
    hist = {10: 1, 50: 4, 80: 4, 99: 1}
    # 目标名次：min=1，q1=ceil(2.5)=3，median=5，q3=ceil(7.5)=8，max=10
    assert five_numbers(hist) == {"game_cnt": 10, "min": 10, "q1": 50, "median": 50, "q3": 80, "max": 99}
    assert five_numbers({42: 1}) == {"game_cnt": 1, "min": 42, "q1": 42, "median": 42, "q3": 42, "max": 42}
    assert five_numbers({}) is None


def _rating(year, genre, bucket, rbin, cnt):
    return dict(release_year=year, genre=genre, price_bucket=bucket, rating_bin=rbin, game_cnt=cnt)


def test_price_rating(client, seed):
    seed(T.ads_yearly_release, yearly_rows())
    seed(T.ads_rating_dist, [
        _rating(2023, "__ALL__", "ge60", 90, 2),
        _rating(2023, "__ALL__", "free", 10, 1),
        _rating(2024, "__ALL__", "free", 50, 4),
        _rating(2024, "__ALL__", "free", 80, 4),
        _rating(2024, "__ALL__", "free", 99, 1),
        _rating(2024, "Action", "free", 70, 5),
    ])
    data = ok_data(client.get("/api/v1/trend/price-rating"))
    # 两个年份的分箱先相加再求五数；按固定档位顺序返回，没有游戏的档位不返回
    assert data == [
        {"price_bucket": "free", "game_cnt": 10, "min": 10, "q1": 50, "median": 50, "q3": 80, "max": 99},
        {"price_bucket": "ge60", "game_cnt": 2, "min": 90, "q1": 90, "median": 90, "q3": 90, "max": 90},
    ]
    action = ok_data(client.get("/api/v1/trend/price-rating", params={"genre": "Action"}))
    assert action == [{"price_bucket": "free", "game_cnt": 5, "min": 70, "q1": 70, "median": 70, "q3": 70, "max": 70}]


def test_price_rating_empty(client):
    assert ok_data(client.get("/api/v1/trend/price-rating")) == []


def test_price_rating_invalid(client):
    assert_bad_param(client.get("/api/v1/trend/price-rating", params={"year_start": 2026, "year_end": 2025}))
