"""数据库连接：只用只读账号 api_reader 连 steam 库（dwd / ads 两层）。

每个请求从连接池借一个 Connection，请求结束归还。后端只读，不开事务写入。
"""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import URL, Connection, Engine, create_engine

from .core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    s = get_settings()
    url = URL.create(
        "mysql+pymysql",
        username=s.db_user,
        password=s.db_password,  # URL.create 会转义密码里的特殊字符
        host=s.db_host,
        port=s.db_port,
        database=s.db_name,
        query={"charset": "utf8mb4"},
    )
    return create_engine(
        url,
        pool_pre_ping=True,   # 主库重启或闲置断开后自动重连
        pool_recycle=3600,
        pool_size=5,
        max_overflow=5,
        connect_args={"connect_timeout": 5, "read_timeout": 30},
    )


def get_conn() -> Iterator[Connection]:
    """FastAPI 依赖：每个请求一个连接。测试里用 dependency_overrides 换成 SQLite。"""
    with get_engine().connect() as conn:
        yield conn
