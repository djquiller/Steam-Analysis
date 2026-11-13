"""测试夹具：每个测试一个内存 SQLite 库，按 app/tables.py 建表，只插测试需要的几行。

为什么不用样本库：storage/sample/seed_sample.sql 还没导出；而且要覆盖"正常 / 空 / 非法"三种情况，
需要精确可控的数据。查询都用 SQLAlchemy Core 写成通用 SQL，所以 SQLite 上的结果能代表 MySQL。
对真实库的冒烟测试在 test_live_db.py（连不上就跳过）。
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, insert
from sqlalchemy.pool import StaticPool

from app import tables as T
from app.db import get_conn
from app.main import app
from app.services.filters import genre_catalog


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    T.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def client(engine):
    def _conn():
        with engine.connect() as conn:
            yield conn

    genre_catalog.clear()
    app.dependency_overrides[get_conn] = _conn
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()
    genre_catalog.clear()


@pytest.fixture
def seed(engine):
    """seed(table, rows)：往测试库里插几行。"""

    def _seed(table, rows):
        with engine.begin() as conn:
            conn.execute(insert(table), rows)

    return _seed


def ok_data(resp):
    """断言成功信封并返回 data。"""
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0 and body["msg"] == "ok", body
    return body["data"]


def assert_bad_param(resp):
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["code"] == 40001 and body["data"] is None, body
    return body["msg"]
