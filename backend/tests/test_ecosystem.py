"""/ecosystem/rating-dist、review-languages、playtime-dist、activity-heatmap。"""

import pytest
from conftest import assert_bad_param, ok_data

from app import tables as T


def _dims(year=2024, genre="__ALL__", bucket="lt10"):
    return dict(release_year=year, genre=genre, price_bucket=bucket)


def test_rating_dist_merges_bins(client, seed):
    seed(T.ads_rating_dist, [
        {**_dims(), "rating_bin": 0, "game_cnt": 1},
        {**_dims(), "rating_bin": 4, "game_cnt": 2},
        {**_dims(2023), "rating_bin": 7, "game_cnt": 3},
        {**_dims(), "rating_bin": 99, "game_cnt": 4},
    ])
    d5 = ok_data(client.get("/api/v1/ecosystem/rating-dist"))
    assert d5["bin_width"] == 5 and d5["game_cnt"] == 10 and len(d5["bins"]) == 20
    assert d5["bins"][0] == {"bin_start": 0, "bin_end": 5, "game_cnt": 3}
    assert d5["bins"][1] == {"bin_start": 5, "bin_end": 10, "game_cnt": 3}
    assert d5["bins"][-1] == {"bin_start": 95, "bin_end": 100, "game_cnt": 4}
    d1 = ok_data(client.get("/api/v1/ecosystem/rating-dist", params={"bin_width": 1}))
    assert len(d1["bins"]) == 100 and d1["bins"][4]["game_cnt"] == 2


def test_rating_dist_empty(client):
    data = ok_data(client.get("/api/v1/ecosystem/rating-dist", params={"bin_width": 10}))
    assert data["game_cnt"] == 0 and len(data["bins"]) == 10 and all(b["game_cnt"] == 0 for b in data["bins"])


@pytest.mark.parametrize("w", [0, 3, 20, "five"])
def test_rating_dist_invalid(client, w):
    assert_bad_param(client.get("/api/v1/ecosystem/rating-dist", params={"bin_width": w}))


def test_review_languages_top_n_and_other(client, seed):
    seed(T.ads_review_lang, [
        {**_dims(), "language": "english", "review_cnt": 50, "positive_cnt": 40},
        {**_dims(), "language": "schinese", "review_cnt": 30, "positive_cnt": 15},
        {**_dims(), "language": "russian", "review_cnt": 15, "positive_cnt": 15},
        {**_dims(2023), "language": "german", "review_cnt": 5, "positive_cnt": 0},
    ])
    data = ok_data(client.get("/api/v1/ecosystem/review-languages", params={"limit": 2}))
    assert data == {
        "review_cnt": 100,
        "items": [
            {"language": "english", "review_cnt": 50, "positive_cnt": 40, "positive_rate": 0.8, "share": 0.5},
            {"language": "schinese", "review_cnt": 30, "positive_cnt": 15, "positive_rate": 0.5, "share": 0.3},
            {"language": "other", "review_cnt": 20, "positive_cnt": 15, "positive_rate": 0.75, "share": 0.2},
        ],
    }
    # 语言数不超过 limit 时没有 other
    data = ok_data(client.get("/api/v1/ecosystem/review-languages"))
    assert [i["language"] for i in data["items"]] == ["english", "schinese", "russian", "german"]


def test_review_languages_empty(client):
    assert ok_data(client.get("/api/v1/ecosystem/review-languages")) == {"review_cnt": 0, "items": []}


def test_review_languages_invalid(client):
    assert_bad_param(client.get("/api/v1/ecosystem/review-languages", params={"limit": 31}))


def test_playtime_dist(client, seed):
    seed(T.ads_playtime_dist, [
        {**_dims(), "playtime_bin": 0, "review_cnt": 7},
        {**_dims(), "playtime_bin": 10, "review_cnt": 3},
    ])
    data = ok_data(client.get("/api/v1/ecosystem/playtime-dist"))
    assert data["review_cnt"] == 10 and len(data["bins"]) == 11
    assert data["bins"][0] == {"bin": 0, "min_hours": 0, "max_hours": 1, "review_cnt": 7}
    assert data["bins"][2] == {"bin": 2, "min_hours": 2, "max_hours": 5, "review_cnt": 0}
    assert data["bins"][10] == {"bin": 10, "min_hours": 1000, "max_hours": None, "review_cnt": 3}


def test_playtime_dist_empty(client):
    data = ok_data(client.get("/api/v1/ecosystem/playtime-dist"))
    assert data["review_cnt"] == 0 and len(data["bins"]) == 11


def test_playtime_dist_invalid(client):
    assert_bad_param(client.get("/api/v1/ecosystem/playtime-dist", params={"price_bucket": "free,xx"}))


def test_activity_heatmap(client, seed):
    seed(T.ads_review_heatmap, [
        {**_dims(), "weekday": 0, "hour": 0, "review_cnt": 5},
        {**_dims(2023), "weekday": 0, "hour": 0, "review_cnt": 5},
        {**_dims(), "weekday": 6, "hour": 23, "review_cnt": 2},
    ])
    data = ok_data(client.get("/api/v1/ecosystem/activity-heatmap"))
    assert data["timezone"] == "UTC" and data["review_cnt"] == 12 and data["max_cnt"] == 10
    assert len(data["cells"]) == 168
    assert data["cells"][0] == {"weekday": 0, "hour": 0, "review_cnt": 10}
    assert data["cells"][-1] == {"weekday": 6, "hour": 23, "review_cnt": 2}
    assert data["cells"][1] == {"weekday": 0, "hour": 1, "review_cnt": 0}


def test_activity_heatmap_empty(client):
    data = ok_data(client.get("/api/v1/ecosystem/activity-heatmap"))
    assert data["review_cnt"] == 0 and data["max_cnt"] == 0 and len(data["cells"]) == 168


def test_activity_heatmap_invalid(client):
    assert_bad_param(client.get("/api/v1/ecosystem/activity-heatmap", params={"genre": "Nope"}))
