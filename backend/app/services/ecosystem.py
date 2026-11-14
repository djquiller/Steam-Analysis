"""/ecosystem/*：好评率分布、评论语言、游玩时长、活跃时段。"""

from sqlalchemy import Connection, func, select

from ..fmt import ratio
from ..tables import ads_playtime_dist, ads_rating_dist, ads_review_heatmap, ads_review_lang
from .filters import Filters

RATING_BIN_WIDTHS = (1, 5, 10)

# 时长分箱的下界（小时），与 docs/schema.md ads_playtime_dist 的分箱表一致；第 11 箱无上界
PLAYTIME_EDGES_HOURS = [0, 1, 2, 5, 10, 20, 50, 100, 200, 500, 1000]


def rating_dist(conn: Connection, f: Filters, bin_width: int) -> dict:
    t = ads_rating_dist
    rows = conn.execute(
        select(t.c.rating_bin, func.sum(t.c.game_cnt)).where(*f.agg_where(t)).group_by(t.c.rating_bin)
    ).all()
    merged = [0] * (100 // bin_width)
    for rbin, cnt in rows:
        idx = min(int(rbin), 99) // bin_width
        merged[idx] += int(cnt or 0)
    return {
        "bin_width": bin_width,
        "game_cnt": sum(merged),
        "bins": [
            {"bin_start": i * bin_width, "bin_end": (i + 1) * bin_width, "game_cnt": c} for i, c in enumerate(merged)
        ],
    }


def review_languages(conn: Connection, f: Filters, limit: int) -> dict:
    t = ads_review_lang
    cnt = func.sum(t.c.review_cnt).label("cnt")
    rows = conn.execute(
        select(t.c.language, cnt, func.sum(t.c.positive_cnt).label("pos"))
        .where(*f.agg_where(t))
        .group_by(t.c.language)
        .order_by(cnt.desc(), t.c.language)
    ).all()
    rows = [(r.language, int(r.cnt or 0), int(r.pos or 0)) for r in rows if r.cnt]
    total = sum(c for _, c, _ in rows)

    def item(lang: str, c: int, p: int) -> dict:
        return {"language": lang, "review_cnt": c, "positive_cnt": p,
                "positive_rate": ratio(p, c), "share": ratio(c, total)}

    items = [item(*r) for r in rows[:limit]]
    rest = rows[limit:]
    if rest:
        items.append(item("other", sum(c for _, c, _ in rest), sum(p for _, _, p in rest)))
    return {"review_cnt": total, "items": items}


def playtime_dist(conn: Connection, f: Filters) -> dict:
    t = ads_playtime_dist
    counts = dict(conn.execute(
        select(t.c.playtime_bin, func.sum(t.c.review_cnt)).where(*f.agg_where(t)).group_by(t.c.playtime_bin)
    ).all())
    bins = []
    for i, lo in enumerate(PLAYTIME_EDGES_HOURS):
        hi = PLAYTIME_EDGES_HOURS[i + 1] if i + 1 < len(PLAYTIME_EDGES_HOURS) else None
        bins.append({"bin": i, "min_hours": lo, "max_hours": hi, "review_cnt": int(counts.get(i) or 0)})
    return {"review_cnt": sum(b["review_cnt"] for b in bins), "bins": bins}


def activity_heatmap(conn: Connection, f: Filters) -> dict:
    t = ads_review_heatmap
    counts = {
        (int(w), int(h)): int(c or 0)
        for w, h, c in conn.execute(
            select(t.c.weekday, t.c.hour, func.sum(t.c.review_cnt)).where(*f.agg_where(t)).group_by(t.c.weekday, t.c.hour)
        ).all()
    }
    cells = [{"weekday": w, "hour": h, "review_cnt": counts.get((w, h), 0)} for w in range(7) for h in range(24)]
    return {
        "timezone": "UTC",
        "review_cnt": sum(c["review_cnt"] for c in cells),
        "max_cnt": max(c["review_cnt"] for c in cells),
        "cells": cells,
    }
