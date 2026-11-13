"""后端读取的 dwd / ads 表的 SQLAlchemy 定义。

字段类型的权威来源是 scripts/init_db.sql，口径见 docs/schema.md；这里只声明后端要读的列，
用通用类型（Integer / Numeric …），这样查询既能在 MySQL 上跑，也能在测试用的 SQLite 上跑。
后端不建表，metadata.create_all 只在测试里调用。
"""

from sqlalchemy import (
    BigInteger, Column, Date, DateTime, Float, Integer, MetaData, Numeric, SmallInteger, String, Table,
)

metadata = MetaData()


def _dims() -> list[Column]:
    """聚合表共有的三个筛选维度列，排在主键最前面。"""
    return [
        Column("release_year", SmallInteger, primary_key=True),
        Column("genre", String(64), primary_key=True),
        Column("price_bucket", String(8), primary_key=True),
    ]


# ---------------------------------------------------------------- dwd
dwd_game = Table(
    "dwd_game", metadata,
    Column("appid", Integer, primary_key=True),
    Column("name", String(512), nullable=False),
    Column("release_date", Date),
    Column("release_year", SmallInteger),
    Column("price_usd", Numeric(10, 2), nullable=False),
    Column("price_bucket", String(8), nullable=False),
    Column("owners_low", Integer),
    Column("owners_high", Integer),
    Column("owners_mid", Integer),
    Column("peak_ccu", Integer),
    Column("positive", Integer, nullable=False),
    Column("negative", Integer, nullable=False),
    Column("avg_playtime_min", Integer),
    Column("median_playtime_min", Integer),
    Column("required_age", Integer),
    Column("dlc_count", Integer),
    Column("achievements", Integer),
    Column("num_languages", Integer),
    Column("on_windows", Integer),
    Column("on_mac", Integer),
    Column("on_linux", Integer),
    Column("metacritic_score", Integer),
    Column("developer", String(255)),
    Column("publisher", String(255)),
    Column("header_image", String(1024)),
)

dwd_game_genre = Table(
    "dwd_game_genre", metadata,
    Column("appid", Integer, primary_key=True),
    Column("genre", String(64), primary_key=True),
)

dwd_price_history = Table(
    "dwd_price_history", metadata,
    Column("appid", Integer, primary_key=True),
    Column("snapshot_date", Date, primary_key=True),
    Column("price_usd", Numeric(10, 2), nullable=False),
)

# ---------------------------------------------------------------- ads：全局
ads_kpi_overview = Table(
    "ads_kpi_overview", metadata,
    Column("id", Integer, primary_key=True),
    Column("game_cnt", Integer, nullable=False),
    Column("review_cnt", BigInteger),
    Column("owners_total", BigInteger, nullable=False),
    Column("online_peak_24h", Integer),
    Column("online_peak_at", DateTime),
    Column("updated_at", DateTime, nullable=False),
)

ads_meta = Table(
    "ads_meta", metadata,
    Column("meta_key", String(64), primary_key=True),
    Column("meta_value", String(255), nullable=False),
    Column("updated_at", DateTime, nullable=False),
)

ads_ccu_latest = Table(
    "ads_ccu_latest", metadata,
    Column("appid", Integer, primary_key=True),
    Column("name", String(512), nullable=False),
    Column("player_count", Integer, nullable=False),
    Column("player_count_prev", Integer),
    Column("snapshot_at", DateTime, nullable=False),
)

ads_game_review_trend = Table(
    "ads_game_review_trend", metadata,
    Column("appid", Integer, primary_key=True),
    Column("month_start", Date, primary_key=True),
    Column("review_cnt", Integer, nullable=False),
    Column("positive_cnt", Integer, nullable=False),
)

ads_hot_pred = Table(
    "ads_hot_pred", metadata,
    Column("appid", Integer, primary_key=True),
    Column("hot_prob", Numeric(5, 4), nullable=False),
    Column("hot_pred", Integer, nullable=False),
    Column("hot_actual", Integer, nullable=False),
    Column("is_test", Integer, nullable=False),
    Column("model_name", String(32), nullable=False),
)

ads_review_sentiment = Table(
    "ads_review_sentiment", metadata,
    Column("appid", Integer, primary_key=True),
    Column("sample_cnt", Integer, nullable=False),
    Column("positive_cnt", Integer, nullable=False),
    Column("method", String(16), nullable=False),
)

# ---------------------------------------------------------------- ads：游戏粒度（筛类型时关联 dwd_game_genre）
ads_top_sellers = Table(
    "ads_top_sellers", metadata,
    Column("appid", Integer, primary_key=True),
    Column("name", String(512), nullable=False),
    Column("release_year", SmallInteger, nullable=False),
    Column("price_bucket", String(8), nullable=False),
    Column("price_usd", Numeric(10, 2), nullable=False),
    Column("owners_mid", Integer),
    Column("review_cnt", Integer, nullable=False),
    Column("positive_cnt", Integer, nullable=False),
    Column("peak_ccu", Integer),
    Column("ccu_latest", Integer),
    Column("ccu_at", DateTime),
)

ads_game_cluster = Table(
    "ads_game_cluster", metadata,
    Column("appid", Integer, primary_key=True),
    Column("name", String(512), nullable=False),
    Column("release_year", SmallInteger, nullable=False),
    Column("price_bucket", String(8), nullable=False),
    Column("cluster_id", Integer, nullable=False),
    Column("cluster_label", String(32), nullable=False),
    Column("x", Float, nullable=False),
    Column("y", Float, nullable=False),
    Column("price_usd", Numeric(10, 2), nullable=False),
    Column("positive_rate", Numeric(5, 4), nullable=False),
    Column("owners_mid", Integer, nullable=False),
    Column("avg_playtime_min", Integer, nullable=False),
    Column("sample_key", BigInteger, nullable=False),
)

# ---------------------------------------------------------------- ads：聚合（含 genre='__ALL__' 汇总行，ads_genre_heat 除外）
ads_yearly_release = Table(
    "ads_yearly_release", metadata, *_dims(),
    Column("game_cnt", Integer, nullable=False),
    Column("price_sum", Numeric(14, 2), nullable=False),
)

ads_genre_heat = Table(
    "ads_genre_heat", metadata, *_dims(),
    Column("game_cnt", Integer, nullable=False),
    Column("owners_sum", BigInteger, nullable=False),
    Column("review_cnt", BigInteger, nullable=False),
    Column("positive_cnt", BigInteger, nullable=False),
)

ads_rating_dist = Table(
    "ads_rating_dist", metadata, *_dims(),
    Column("rating_bin", Integer, primary_key=True),
    Column("game_cnt", Integer, nullable=False),
)

ads_review_lang = Table(
    "ads_review_lang", metadata, *_dims(),
    Column("language", String(32), primary_key=True),
    Column("review_cnt", BigInteger, nullable=False),
    Column("positive_cnt", BigInteger, nullable=False),
)

ads_playtime_dist = Table(
    "ads_playtime_dist", metadata, *_dims(),
    Column("playtime_bin", Integer, primary_key=True),
    Column("review_cnt", BigInteger, nullable=False),
)

ads_review_heatmap = Table(
    "ads_review_heatmap", metadata, *_dims(),
    Column("weekday", Integer, primary_key=True),
    Column("hour", Integer, primary_key=True),
    Column("review_cnt", BigInteger, nullable=False),
)
