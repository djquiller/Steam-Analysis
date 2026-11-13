"""/trend/*：历年发行、类型热度、价格区间 × 好评率箱线。"""

import math

from sqlalchemy import Connection, func, select

from ..fmt import money, ratio
from ..tables import ads_genre_heat, ads_rating_dist, ads_yearly_release
from .filters import PRICE_BUCKET_KEYS, Filters


def yearly(conn: Connection, f: Filters) -> list[dict]:
    t = ads_yearly_release
    rows = conn.execute(
        select(t.c.release_year, func.sum(t.c.game_cnt).label("cnt"), func.sum(t.c.price_sum).label("ps"))
        .where(*f.agg_where(t))
        .group_by(t.c.release_year)
        .order_by(t.c.release_year)
    ).all()
    out = []
    for year, cnt, ps in rows:
        cnt = int(cnt or 0)
        if cnt == 0:
            continue
        out.append({
            "year": int(year),
            "game_cnt": cnt,
            "price_sum": money(ps or 0),
            "avg_price_usd": money(float(ps or 0) / cnt),
        })
    return out


def genres(conn: Connection, f: Filters) -> list[dict]:
    t = ads_genre_heat
    cnt = func.sum(t.c.game_cnt).label("cnt")
    rows = conn.execute(
        select(t.c.genre, cnt, func.sum(t.c.owners_sum).label("owners"),
               func.sum(t.c.review_cnt).label("reviews"), func.sum(t.c.positive_cnt).label("pos"))
        .where(*f.genre_heat_where(t))
        .group_by(t.c.genre)
        .order_by(cnt.desc(), t.c.genre)
    ).all()
    return [
        {
            "genre": r.genre,
            "game_cnt": int(r.cnt or 0),
            "owners_sum": int(r.owners or 0),
            "review_cnt": int(r.reviews or 0),
            "positive_cnt": int(r.pos or 0),
            "positive_rate": ratio(r.pos, r.reviews),
        }
        for r in rows
        if r.cnt
    ]


def five_numbers(hist: dict[int, int]) -> dict | None:
    """由 1% 分箱的计数推算箱线图五数。

    分位数 p 取"累计计数第一次达到 ceil(p × 总数)（至少为 1）时所在的分箱"，
    p = 0 即最小非空分箱，p = 1 即最大非空分箱（docs/api.md /trend/price-rating）。
    """
    total = sum(hist.values())
    if total <= 0:
        return None
    targets = {name: max(1, math.ceil(p * total))
               for name, p in (("min", 0), ("q1", 0.25), ("median", 0.5), ("q3", 0.75), ("max", 1))}
    out: dict[str, int] = {}
    cum = 0
    for b in sorted(hist):
        cum += hist[b]
        for name, target in targets.items():
            if name not in out and cum >= target:
                out[name] = b
    return {"game_cnt": total, **out}


def price_rating(conn: Connection, f: Filters) -> list[dict]:
    t = ads_rating_dist
    rows = conn.execute(
        select(t.c.price_bucket, t.c.rating_bin, func.sum(t.c.game_cnt))
        .where(*f.agg_where(t))
        .group_by(t.c.price_bucket, t.c.rating_bin)
    ).all()
    hists: dict[str, dict[int, int]] = {}
    for bucket, rbin, cnt in rows:
        hists.setdefault(bucket, {})[int(rbin)] = int(cnt or 0)
    out = []
    for bucket in PRICE_BUCKET_KEYS:
        box = five_numbers(hists.get(bucket, {}))
        if box:
            out.append({"price_bucket": bucket, **box})
    return out
