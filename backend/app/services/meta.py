"""/meta/* 与 /overview/kpi：筛选项、更新时间、KPI。"""

from datetime import datetime

from sqlalchemy import Connection, func, select

from ..fmt import iso, to_int
from ..tables import ads_kpi_overview, ads_meta, ads_yearly_release
from .filters import ALL_GENRES, PRICE_BUCKETS


def filters(conn: Connection) -> dict:
    t = ads_yearly_release
    # 年份范围与各价格区间的游戏数读 __ALL__ 行（每款游戏只计一次）
    yr = conn.execute(
        select(func.min(t.c.release_year), func.max(t.c.release_year)).where(t.c.genre == ALL_GENRES)
    ).one()
    by_bucket = dict(conn.execute(
        select(t.c.price_bucket, func.sum(t.c.game_cnt)).where(t.c.genre == ALL_GENRES).group_by(t.c.price_bucket)
    ).all())
    cnt = func.sum(t.c.game_cnt).label("cnt")
    genres = conn.execute(
        select(t.c.genre, cnt).where(t.c.genre != ALL_GENRES).group_by(t.c.genre).order_by(cnt.desc(), t.c.genre)
    ).all()
    return {
        "years": {"min": to_int(yr[0]), "max": to_int(yr[1])},
        "genres": [{"genre": g, "game_cnt": int(c)} for g, c in genres],
        "price_buckets": [
            {"key": k, "label": label, "game_cnt": int(by_bucket.get(k) or 0)} for k, label in PRICE_BUCKETS
        ],
    }


def _meta_time(value: str | None) -> str | None:
    """ads_meta 的时间值存成 'YYYY-MM-DD HH:MM:SS'（UTC），转成 ISO 8601。"""
    if not value:
        return None
    try:
        return iso(datetime.fromisoformat(value))
    except ValueError:
        return None


def updated_at(conn: Connection) -> dict:
    t = ads_meta
    rows = conn.execute(select(t.c.meta_key, t.c.meta_value, t.c.updated_at).order_by(t.c.meta_key)).all()
    values = {r.meta_key: r.meta_value for r in rows}
    tables = []
    for r in rows:
        if r.meta_key.startswith("rows."):
            try:
                n = int(r.meta_value)
            except ValueError:
                continue  # 登记坏了的行数不展示，免得整个接口报错
            tables.append({"table": r.meta_key[len("rows."):], "rows": n, "updated_at": iso(r.updated_at)})
    return {
        "data_updated_at": _meta_time(values.get("data_updated_at")),
        "ccu_updated_at": _meta_time(values.get("ccu_updated_at")),
        "tables": tables,
    }


def kpi(conn: Connection) -> dict:
    t = ads_kpi_overview
    r = conn.execute(select(t).where(t.c.id == 1)).first()
    if r is None:
        return {}
    return {
        "game_cnt": int(r.game_cnt),
        "review_cnt": to_int(r.review_cnt),
        "owners_total": int(r.owners_total),
        "online_peak_24h": to_int(r.online_peak_24h),
        "online_peak_at": iso(r.online_peak_at),
        "updated_at": iso(r.updated_at),
    }
