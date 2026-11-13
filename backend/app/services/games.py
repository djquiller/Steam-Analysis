"""/games/{appid}*：单款游戏详情、评论月度走势、价格历史。"""

from sqlalchemy import Connection, func, select

from ..errors import not_found
from ..fmt import game_rate, iso_date, money, ratio, to_int
from ..tables import (
    ads_game_cluster, ads_game_review_trend, ads_hot_pred, ads_review_sentiment, dwd_game, dwd_game_genre,
    dwd_price_history,
)


def _require_game(conn: Connection, appid: int) -> None:
    if conn.execute(select(dwd_game.c.appid).where(dwd_game.c.appid == appid)).first() is None:
        raise not_found(f"游戏不存在：appid={appid}")


def detail(conn: Connection, appid: int) -> dict:
    g = conn.execute(select(dwd_game).where(dwd_game.c.appid == appid)).first()
    if g is None:
        raise not_found(f"游戏不存在：appid={appid}")

    genres = conn.execute(
        select(dwd_game_genre.c.genre).where(dwd_game_genre.c.appid == appid).order_by(dwd_game_genre.c.genre)
    ).scalars().all()
    platforms = [p for p, flag in (("windows", g.on_windows), ("mac", g.on_mac), ("linux", g.on_linux)) if flag]
    review_cnt = int(g.positive or 0) + int(g.negative or 0)

    c = ads_game_cluster
    cl = conn.execute(select(c.c.cluster_id, c.c.cluster_label).where(c.c.appid == appid)).first()
    cluster = peers = None
    if cl is not None:
        cluster = {"cluster_id": int(cl.cluster_id), "cluster_label": cl.cluster_label}
        p = conn.execute(
            select(func.count().label("n"), func.avg(c.c.price_usd).label("price"),
                   func.avg(c.c.positive_rate).label("rate"), func.avg(c.c.owners_mid).label("owners"),
                   func.avg(c.c.avg_playtime_min).label("playtime"))
            .where(c.c.cluster_id == cl.cluster_id)
        ).one()
        peers = {
            **cluster,
            "game_cnt": int(p.n),
            "avg_price_usd": money(p.price),
            "avg_positive_rate": round(float(p.rate), 4),
            "avg_owners_mid": int(round(float(p.owners))),
            "avg_playtime_min": int(round(float(p.playtime))),
        }

    h = conn.execute(select(ads_hot_pred).where(ads_hot_pred.c.appid == appid)).first()
    hot_pred = None if h is None else {
        "hot_prob": round(float(h.hot_prob), 4),
        "hot_pred": bool(h.hot_pred),
        "hot_actual": bool(h.hot_actual),
        "is_test": bool(h.is_test),
        "model_name": h.model_name,
    }

    s = conn.execute(select(ads_review_sentiment).where(ads_review_sentiment.c.appid == appid)).first()
    sentiment = None if s is None else {
        "sample_cnt": int(s.sample_cnt),
        "positive_cnt": int(s.positive_cnt),
        "positive_ratio": ratio(s.positive_cnt, s.sample_cnt),
        "method": s.method,
    }

    return {
        "appid": int(g.appid),
        "name": g.name,
        "header_image": g.header_image,
        "release_date": iso_date(g.release_date),
        "release_year": to_int(g.release_year),
        "price_usd": money(g.price_usd),
        "price_bucket": g.price_bucket,
        "genres": list(genres),
        "developer": g.developer,
        "publisher": g.publisher,
        "owners_low": to_int(g.owners_low),
        "owners_high": to_int(g.owners_high),
        "owners_mid": to_int(g.owners_mid),
        "peak_ccu": to_int(g.peak_ccu),
        "review_cnt": review_cnt,
        "positive_cnt": int(g.positive or 0),
        "positive_rate": game_rate(int(g.positive or 0), review_cnt),
        "avg_playtime_min": to_int(g.avg_playtime_min),
        "median_playtime_min": to_int(g.median_playtime_min),
        "metacritic_score": to_int(g.metacritic_score),
        "required_age": to_int(g.required_age),
        "dlc_count": to_int(g.dlc_count),
        "achievements": to_int(g.achievements),
        "num_languages": to_int(g.num_languages),
        "platforms": platforms,
        "cluster": cluster,
        "hot_pred": hot_pred,
        "sentiment": sentiment,
        "peers": peers,
    }


def reviews_trend(conn: Connection, appid: int) -> list[dict]:
    _require_game(conn, appid)
    t = ads_game_review_trend
    rows = conn.execute(select(t).where(t.c.appid == appid).order_by(t.c.month_start)).all()
    return [
        {
            "month": iso_date(r.month_start)[:7],
            "review_cnt": int(r.review_cnt),
            "positive_cnt": int(r.positive_cnt),
            "positive_rate": ratio(r.positive_cnt, r.review_cnt),
        }
        for r in rows
    ]


def price_history(conn: Connection, appid: int) -> list[dict]:
    _require_game(conn, appid)
    t = dwd_price_history
    rows = conn.execute(select(t).where(t.c.appid == appid).order_by(t.c.snapshot_date)).all()
    return [{"date": iso_date(r.snapshot_date), "price_usd": money(r.price_usd)} for r in rows]
