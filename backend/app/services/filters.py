"""全局筛选参数（年份 / 类型 / 价格区间）的解析与 WHERE 条件生成。

所有可筛选接口都通过 `Depends(get_filters)` 拿到同一个 Filters，再按表的类型取条件：
- 聚合表（带 genre 列）：`agg_where`。没选类型读 genre='__ALL__' 汇总行，选了读该类型的行。
- 游戏粒度表（一款游戏一行）：`game_where`。选了类型才加 EXISTS 关联 dwd_game_genre。
规则见 docs/schema.md "筛选维度约定"。
"""

import time
from dataclasses import dataclass, field
from threading import Lock

from fastapi import Depends, Query
from sqlalchemy import Connection, Table, exists, select

from ..core.config import get_settings
from ..db import get_conn
from ..errors import bad_param
from ..tables import ads_yearly_release, dwd_game_genre

ALL_GENRES = "__ALL__"

# 固定顺序：/meta/filters、/trend/price-rating 都按这个顺序返回
PRICE_BUCKETS: list[tuple[str, str]] = [
    ("free", "免费"),
    ("lt10", "$10 以下"),
    ("10_30", "$10–30"),
    ("30_60", "$30–60"),
    ("ge60", "$60 及以上"),
]
PRICE_BUCKET_KEYS = [k for k, _ in PRICE_BUCKETS]


@dataclass(frozen=True)
class Filters:
    year_start: int | None = None
    year_end: int | None = None
    genre: str | None = None
    price_buckets: tuple[str, ...] = field(default_factory=tuple)

    def _common(self, t: Table) -> list:
        conds = []
        if self.year_start is not None:
            conds.append(t.c.release_year >= self.year_start)
        if self.year_end is not None:
            conds.append(t.c.release_year <= self.year_end)
        if self.price_buckets:
            conds.append(t.c.price_bucket.in_(self.price_buckets))
        return conds

    def agg_where(self, t: Table) -> list:
        """聚合表：年份、价格区间，加上 genre = 所选类型或 '__ALL__'。"""
        return [t.c.genre == (self.genre or ALL_GENRES), *self._common(t)]

    def genre_heat_where(self, t: Table) -> list:
        """ads_genre_heat：按类型展示全部类型，只按年份、价格区间过滤，不看 genre。"""
        return self._common(t)

    def game_where(self, t: Table) -> list:
        """游戏粒度表：年份、价格区间；选了类型时用 EXISTS 关联 dwd_game_genre。"""
        conds = self._common(t)
        if self.genre:
            g = dwd_game_genre
            conds.append(exists(select(1).where(g.c.appid == t.c.appid, g.c.genre == self.genre)))
        return conds


# ---------------------------------------------------------------- genre 合法取值（带缓存）

class _GenreCatalog:
    """缓存 /meta/filters 的类型列表，校验 genre 参数时用，避免每个请求都查一次库。"""

    def __init__(self) -> None:
        self._lock = Lock()
        self._genres: frozenset[str] | None = None
        self._loaded_at = 0.0

    def get(self, conn: Connection) -> frozenset[str]:
        ttl = get_settings().genre_cache_seconds
        with self._lock:
            if self._genres is None or time.monotonic() - self._loaded_at > ttl:
                t = ads_yearly_release
                rows = conn.execute(select(t.c.genre).where(t.c.genre != ALL_GENRES).distinct())
                self._genres = frozenset(r.genre for r in rows)
                self._loaded_at = time.monotonic()
            return self._genres

    def clear(self) -> None:
        with self._lock:
            self._genres = None


genre_catalog = _GenreCatalog()


def parse_price_buckets(raw: str | None) -> tuple[str, ...]:
    if raw is None or not raw.strip():
        return ()
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    bad = [k for k in keys if k not in PRICE_BUCKET_KEYS]
    if bad:
        raise bad_param(f"price_bucket 取值非法：{', '.join(bad)}；可选 {', '.join(PRICE_BUCKET_KEYS)}")
    # 去重并按固定顺序排列，便于缓存和日志
    return tuple(k for k in PRICE_BUCKET_KEYS if k in keys)


def get_filters(
    year_start: int | None = Query(None, ge=1970, le=2100, description="发行年份下界（含）"),
    year_end: int | None = Query(None, ge=1970, le=2100, description="发行年份上界（含）"),
    genre: str | None = Query(None, max_length=64, description="单个类型名，取值见 /meta/filters；不传表示全部类型"),
    price_bucket: str | None = Query(
        None, description="价格区间，可多选，逗号分隔：free / lt10 / 10_30 / 30_60 / ge60；不传表示全部"),
    conn: Connection = Depends(get_conn),
) -> Filters:
    if year_start is not None and year_end is not None and year_start > year_end:
        raise bad_param("year_start 不能大于 year_end")
    buckets = parse_price_buckets(price_bucket)
    genre = genre.strip() if genre else None
    if genre and genre not in genre_catalog.get(conn):
        raise bad_param(f"genre 取值非法：{genre}；可选值见 /api/v1/meta/filters")
    return Filters(year_start, year_end, genre or None, buckets)
