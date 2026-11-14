"""/meta/filters、/meta/updated-at、/overview/kpi，以及信封与错误处理。"""

from datetime import datetime

from conftest import ok_data
from factories import UTC_NOON, yearly_rows
from sqlalchemy.exc import OperationalError

from app import tables as T
from app.db import get_conn
from app.main import app


def test_meta_filters(client, seed):
    seed(T.ads_yearly_release, yearly_rows())
    data = ok_data(client.get("/api/v1/meta/filters"))
    assert data["years"] == {"min": 2023, "max": 2024}
    assert data["genres"] == [{"genre": "Action", "game_cnt": 11}, {"genre": "RPG", "game_cnt": 2}]
    buckets = {b["key"]: b["game_cnt"] for b in data["price_buckets"]}
    assert [b["key"] for b in data["price_buckets"]] == ["free", "lt10", "10_30", "30_60", "ge60"]
    assert buckets == {"free": 10, "lt10": 50, "10_30": 5, "30_60": 0, "ge60": 0}


def test_meta_filters_empty(client):
    data = ok_data(client.get("/api/v1/meta/filters"))
    assert data["years"] == {"min": None, "max": None}
    assert data["genres"] == []
    assert all(b["game_cnt"] == 0 for b in data["price_buckets"])


def test_updated_at(client, seed):
    t = datetime(2026, 11, 12, 21, 55, 12)
    seed(T.ads_meta, [
        {"meta_key": "data_updated_at", "meta_value": "2026-11-12 21:55:12", "updated_at": t},
        {"meta_key": "rows.dwd_game", "meta_value": "125854", "updated_at": t},
        {"meta_key": "rows.broken", "meta_value": "n/a", "updated_at": t},
    ])
    data = ok_data(client.get("/api/v1/meta/updated-at"))
    assert data == {
        "data_updated_at": "2026-11-12T21:55:12Z",
        "ccu_updated_at": None,
        "tables": [{"table": "dwd_game", "rows": 125854, "updated_at": "2026-11-12T21:55:12Z"}],
    }


def test_updated_at_empty(client):
    assert ok_data(client.get("/api/v1/meta/updated-at")) == {
        "data_updated_at": None, "ccu_updated_at": None, "tables": []}


def test_kpi(client, seed):
    seed(T.ads_kpi_overview, [{"id": 1, "game_cnt": 125853, "review_cnt": None, "owners_total": 10515020000,
                               "online_peak_24h": 3200000, "online_peak_at": UTC_NOON, "updated_at": UTC_NOON}])
    data = ok_data(client.get("/api/v1/overview/kpi"))
    assert data == {"game_cnt": 125853, "review_cnt": None, "owners_total": 10515020000,
                    "online_peak_24h": 3200000, "online_peak_at": "2026-11-12T12:00:00Z",
                    "updated_at": "2026-11-12T12:00:00Z"}


def test_kpi_empty_returns_empty_object(client):
    assert ok_data(client.get("/api/v1/overview/kpi")) == {}


def test_unknown_route_is_enveloped(client):
    r = client.get("/api/v1/nope")
    assert r.status_code == 404 and r.json()["code"] == 40401


def test_health(client):
    assert ok_data(client.get("/health")) == {"status": "up"}


def test_db_error_returns_50001(client):
    def broken():
        raise OperationalError("SELECT 1", {}, Exception("Can't connect to MySQL server"))
        yield  # pragma: no cover

    app.dependency_overrides[get_conn] = broken
    r = client.get("/api/v1/overview/kpi")
    assert r.status_code == 500
    assert r.json() == {"code": 50001, "msg": "数据库异常，请稍后重试", "data": None}


def test_cors_allows_vite_dev_server(client):
    r = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
