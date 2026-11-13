"""测试数据：一组小而完整的样例，数字故意取得好算。"""

from datetime import date, datetime

UTC_NOON = datetime(2026, 11, 12, 12, 0, 0)


def yearly_rows():
    # (year, genre, bucket, game_cnt, price_sum)
    data = [
        (2023, "__ALL__", "free", 10, 0),
        (2023, "__ALL__", "lt10", 20, 100),
        (2024, "__ALL__", "lt10", 30, 150),
        (2024, "__ALL__", "10_30", 5, 100),
        (2023, "Action", "lt10", 8, 40),
        (2024, "Action", "10_30", 3, 60),
        (2024, "RPG", "10_30", 2, 40),
    ]
    return [dict(release_year=y, genre=g, price_bucket=b, game_cnt=c, price_sum=p) for y, g, b, c, p in data]


def game_row(appid, **kw):
    row = dict(
        appid=appid, name=f"Game {appid}", release_date=date(2024, 3, 1), release_year=2024, price_usd=19.99,
        price_bucket="10_30", owners_low=1000, owners_high=3000, owners_mid=2000, peak_ccu=50, positive=90,
        negative=10, avg_playtime_min=120, median_playtime_min=60, required_age=0, dlc_count=1, achievements=10,
        num_languages=3, on_windows=1, on_mac=0, on_linux=1, metacritic_score=None, developer="Dev",
        publisher="Pub", header_image=None,
    )
    row.update(kw)
    return row


def top_seller_row(appid, **kw):
    row = dict(
        appid=appid, name=f"Game {appid}", release_year=2024, price_bucket="10_30", price_usd=19.99, owners_mid=2000,
        review_cnt=100, positive_cnt=90, peak_ccu=50, ccu_latest=None, ccu_at=None,
    )
    row.update(kw)
    return row


def cluster_row(appid, cluster_id, **kw):
    row = dict(
        appid=appid, name=f"Game {appid}", release_year=2024, price_bucket="10_30", cluster_id=cluster_id,
        cluster_label=f"簇{cluster_id}", x=1.0, y=-1.0, price_usd=10.0, positive_rate=0.8, owners_mid=1000,
        avg_playtime_min=100, sample_key=appid * 7 % 101,
    )
    row.update(kw)
    return row
