"""对 .env 配置的真实库（本机全量库或样本库）做冒烟测试：每个接口都能返回 code = 0。

连不上数据库时整个文件自动跳过，所以没有库的机器上也能跑其余测试。
只运行这部分：python -m pytest -m live
"""

import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db import get_engine
from app.main import app
from app.services.filters import genre_catalog

pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def live():
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1 FROM ads_meta LIMIT 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"连不上 .env 配置的数据库：{type(exc).__name__}")
    genre_catalog.clear()
    with TestClient(app) as c:
        yield c
    genre_catalog.clear()


def _first_genre(c) -> str | None:
    genres = c.get("/api/v1/meta/filters").json()["data"]["genres"]
    return genres[-1]["genre"] if genres else None  # 取游戏最少的类型，EXISTS 关联最慢的情况


@pytest.mark.parametrize("path", [
    "/api/v1/meta/filters",
    "/api/v1/meta/updated-at",
    "/api/v1/overview/kpi",
    "/api/v1/trend/yearly",
    "/api/v1/trend/genres",
    "/api/v1/trend/price-rating",
    "/api/v1/rank/top-sellers",
    "/api/v1/rank/top-sellers?metric=ccu",
    "/api/v1/rank/online-live",
    "/api/v1/cluster/games",
    "/api/v1/ecosystem/rating-dist",
    "/api/v1/ecosystem/review-languages",
    "/api/v1/ecosystem/playtime-dist",
    "/api/v1/ecosystem/activity-heatmap",
])
def test_endpoint_ok(live, path):
    r = live.get(path)
    assert r.status_code == 200 and r.json()["code"] == 0, r.text


def test_filtered_endpoints_ok_and_fast(live):
    genre = _first_genre(live)
    if genre is None:
        pytest.skip("ads_yearly_release 为空")
    params = {"genre": genre, "year_start": 2015, "price_bucket": "lt10,10_30"}
    for path in ["/api/v1/trend/yearly", "/api/v1/trend/price-rating", "/api/v1/rank/top-sellers",
                 "/api/v1/cluster/games", "/api/v1/ecosystem/rating-dist"]:
        t0 = time.perf_counter()
        r = live.get(path, params=params)
        elapsed = time.perf_counter() - t0
        assert r.status_code == 200 and r.json()["code"] == 0, r.text
        assert elapsed < 2.0, f"{path} 用了 {elapsed:.2f} 秒"


def test_game_detail_roundtrip(live):
    top = live.get("/api/v1/rank/top-sellers", params={"limit": 1}).json()["data"]
    if not top:
        pytest.skip("ads_top_sellers 为空")
    appid = top[0]["appid"]
    for suffix in ["", "/reviews-trend", "/price-history"]:
        r = live.get(f"/api/v1/games/{appid}{suffix}")
        assert r.status_code == 200 and r.json()["code"] == 0, r.text
