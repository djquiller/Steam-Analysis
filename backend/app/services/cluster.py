"""/cluster/games：聚类散点。"""

from sqlalchemy import Connection, func, select

from ..fmt import money
from ..tables import ads_game_cluster
from .filters import Filters


def games(conn: Connection, f: Filters, limit: int) -> dict:
    t = ads_game_cluster
    where = f.game_where(t)
    clusters = conn.execute(
        select(t.c.cluster_id, func.min(t.c.cluster_label).label("label"), func.count().label("cnt"))
        .where(*where)
        .group_by(t.c.cluster_id)
        .order_by(t.c.cluster_id)
    ).all()
    total = sum(int(c.cnt) for c in clusters)
    # 点多于 limit 时按 sample_key（CRC32(appid)）取一份固定的均匀随机子集，每次刷新看到的点都一样
    points = conn.execute(
        select(t.c.appid, t.c.name, t.c.cluster_id, t.c.x, t.c.y, t.c.price_usd, t.c.positive_rate, t.c.owners_mid)
        .where(*where)
        .order_by(t.c.sample_key, t.c.appid)
        .limit(limit)
    ).all()
    return {
        "total": total,
        "clusters": [
            {"cluster_id": int(c.cluster_id), "cluster_label": c.label, "game_cnt": int(c.cnt)} for c in clusters
        ],
        "points": [
            {
                "appid": int(p.appid),
                "name": p.name,
                "cluster_id": int(p.cluster_id),
                "x": round(float(p.x), 4),
                "y": round(float(p.y), 4),
                "price_usd": money(p.price_usd),
                "positive_rate": round(float(p.positive_rate), 4),
                "owners_mid": int(p.owners_mid),
            }
            for p in points
        ],
    }
