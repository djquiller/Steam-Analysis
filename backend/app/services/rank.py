"""/rank/*：热销 Top N、实时在线榜。"""

from sqlalchemy import Connection, select

from ..fmt import game_rate, iso, money, to_int
from ..tables import ads_ccu_latest, ads_top_sellers
from .filters import Filters


def top_sellers(conn: Connection, f: Filters, metric: str, limit: int) -> list[dict]:
    t = ads_top_sellers
    q = select(t).where(*f.game_where(t))
    if metric == "ccu":
        # 只取有最新在线人数的游戏
        q = q.where(t.c.ccu_latest.is_not(None)).order_by(t.c.ccu_latest.desc(), t.c.appid)
    else:
        # owners_mid 只有十几个取值，同档用评论数排第二；MySQL 降序时 NULL 自然排在最后
        q = q.order_by(t.c.owners_mid.desc(), t.c.review_cnt.desc(), t.c.appid)
    rows = conn.execute(q.limit(limit)).all()
    return [
        {
            "rank": i,
            "appid": int(r.appid),
            "name": r.name,
            "release_year": int(r.release_year),
            "price_usd": money(r.price_usd),
            "owners_mid": to_int(r.owners_mid),
            "ccu_latest": to_int(r.ccu_latest),
            "ccu_at": iso(r.ccu_at),
            "peak_ccu": to_int(r.peak_ccu),
            "review_cnt": int(r.review_cnt),
            "positive_rate": game_rate(r.positive_cnt, r.review_cnt),
        }
        for i, r in enumerate(rows, start=1)
    ]


def online_live(conn: Connection, limit: int) -> dict:
    t = ads_ccu_latest
    rows = conn.execute(select(t).order_by(t.c.player_count.desc(), t.c.appid).limit(limit)).all()
    if not rows:
        return {"snapshot_at": None, "items": []}
    return {
        "snapshot_at": iso(max(r.snapshot_at for r in rows)),
        "items": [
            {
                "rank": i,
                "appid": int(r.appid),
                "name": r.name,
                "player_count": int(r.player_count),
                "player_count_prev": to_int(r.player_count_prev),
            }
            for i, r in enumerate(rows, start=1)
        ],
    }
