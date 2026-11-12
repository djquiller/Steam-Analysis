"""MySQL 连接（ETL 专用的 etl_writer 账号）。"""
from __future__ import annotations

import pymysql

from . import settings


def connect_etl(database: str, *, local_infile: bool = False) -> pymysql.connections.Connection:
    """以 etl_writer 身份连接指定的库。

    local_infile=True 时允许 LOAD DATA LOCAL INFILE（服务器端也要开启 local_infile，
    见 storage/README.md）。字符集固定 utf8mb4，否则评论里的 emoji 会写坏。
    """
    return pymysql.connect(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        user=settings.env("ETL_DB_USER", "etl_writer"),
        password=settings.env("ETL_DB_PASSWORD"),
        database=database,
        charset="utf8mb4",
        local_infile=local_infile,
        autocommit=False,
    )
