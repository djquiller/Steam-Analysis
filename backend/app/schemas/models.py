"""各接口 data 的响应模型，字段与 docs/api.md "data 结构"一一对应。

Swagger（/docs）据此生成文档。字段说明写单位，前端图表标注口径时照抄。
"""

from pydantic import BaseModel, Field


# ---------------------------------------------------------------- meta
class YearRange(BaseModel):
    min: int | None = Field(description="可选的最早发行年份；没有数据时为 null")
    max: int | None = Field(description="可选的最晚发行年份")


class GenreOption(BaseModel):
    genre: str
    game_cnt: int = Field(description="该类型的游戏数（款）")


class PriceBucketOption(BaseModel):
    key: str = Field(description="档位取值：free / lt10 / 10_30 / 30_60 / ge60")
    label: str
    game_cnt: int = Field(description="该档位的游戏数（款）")


class MetaFilters(BaseModel):
    years: YearRange
    genres: list[GenreOption]
    price_buckets: list[PriceBucketOption]


class TableRows(BaseModel):
    table: str
    rows: int
    updated_at: str


class MetaUpdatedAt(BaseModel):
    data_updated_at: str | None
    ccu_updated_at: str | None
    tables: list[TableRows]


# ---------------------------------------------------------------- overview
class Kpi(BaseModel):
    game_cnt: int = Field(description="游戏总数（款）")
    review_cnt: int | None = Field(description="评论总数（条）；评论侧聚合完成前为 null")
    owners_total: int = Field(description="估算玩家总量（份），同一玩家拥有多款会重复计")
    online_peak_24h: int | None = Field(description="近 24 小时采集名单内游戏在线人数之和的最大值（人）")
    online_peak_at: str | None
    updated_at: str


# ---------------------------------------------------------------- trend
class YearlyItem(BaseModel):
    year: int
    game_cnt: int = Field(description="发行量（款）")
    price_sum: float = Field(description="价格合计（美元）")
    avg_price_usd: float | None = Field(description="均价（美元），含免费游戏")


class GenreHeatItem(BaseModel):
    genre: str
    game_cnt: int = Field(description="游戏数（款），多类型游戏在每个类型下各计一次")
    owners_sum: int = Field(description="拥有者合计（份）")
    review_cnt: int = Field(description="评论数（条），Steam 官方好评 + 差评")
    positive_cnt: int = Field(description="好评数（条）")
    positive_rate: float | None = Field(description="按评论计的好评占比，0–1")


class PriceRatingBox(BaseModel):
    price_bucket: str
    game_cnt: int = Field(description="参与统计的游戏数（款），评论数 ≥ 10")
    min: int = Field(description="好评率最小值所在分箱下界（%）")
    q1: int
    median: int
    q3: int
    max: int


# ---------------------------------------------------------------- rank
class TopSellerItem(BaseModel):
    rank: int
    appid: int
    name: str
    release_year: int
    price_usd: float = Field(description="美元")
    owners_mid: int | None = Field(description="拥有者（份），SteamSpy 区间估算中值")
    ccu_latest: int | None = Field(description="最新在线人数（人）")
    ccu_at: str | None
    peak_ccu: int | None = Field(description="历史峰值在线（人）")
    review_cnt: int = Field(description="评论数（条）")
    positive_rate: float | None = Field(description="好评率；评论数 < 10 时为 null")


class OnlineLiveItem(BaseModel):
    rank: int
    appid: int
    name: str
    player_count: int = Field(description="当前在线人数（人）")
    player_count_prev: int | None = Field(description="上一个采集时刻的在线人数（人）")


class OnlineLive(BaseModel):
    snapshot_at: str | None
    items: list[OnlineLiveItem]


# ---------------------------------------------------------------- cluster
class ClusterSummary(BaseModel):
    cluster_id: int
    cluster_label: str
    game_cnt: int


class ClusterPoint(BaseModel):
    appid: int
    name: str
    cluster_id: int
    x: float
    y: float
    price_usd: float
    positive_rate: float
    owners_mid: int


class ClusterGames(BaseModel):
    total: int = Field(description="符合筛选的游戏数（款）")
    clusters: list[ClusterSummary]
    points: list[ClusterPoint]


# ---------------------------------------------------------------- ecosystem
class RatingBin(BaseModel):
    bin_start: int = Field(description="分箱下界（%，含）")
    bin_end: int = Field(description="分箱上界（%，不含；最后一箱含 100%）")
    game_cnt: int


class RatingDist(BaseModel):
    bin_width: int
    game_cnt: int = Field(description="参与统计的游戏总数（款），评论数 ≥ 10")
    bins: list[RatingBin]


class LanguageItem(BaseModel):
    language: str = Field(description="Steam 语言代码，或 other")
    review_cnt: int
    positive_cnt: int
    positive_rate: float | None
    share: float | None = Field(description="占评论总数的比例")


class ReviewLanguages(BaseModel):
    review_cnt: int
    items: list[LanguageItem]


class PlaytimeBin(BaseModel):
    bin: int
    min_hours: int
    max_hours: int | None = Field(description="不含；最后一箱为 null，表示 1000 小时及以上")
    review_cnt: int


class PlaytimeDist(BaseModel):
    review_cnt: int
    bins: list[PlaytimeBin]


class HeatCell(BaseModel):
    weekday: int = Field(description="0 = 周一 … 6 = 周日（UTC）")
    hour: int = Field(description="0–23（UTC）")
    review_cnt: int


class ActivityHeatmap(BaseModel):
    timezone: str = "UTC"
    review_cnt: int
    max_cnt: int
    cells: list[HeatCell]


# ---------------------------------------------------------------- games
class GameCluster(BaseModel):
    cluster_id: int
    cluster_label: str


class GameHotPred(BaseModel):
    hot_prob: float
    hot_pred: bool
    hot_actual: bool
    is_test: bool = Field(description="false 表示模型训练时见过这款游戏")
    model_name: str


class GameSentiment(BaseModel):
    sample_cnt: int
    positive_cnt: int
    positive_ratio: float | None
    method: str = Field(description="model 或 voted_up")


class GamePeers(BaseModel):
    cluster_id: int
    cluster_label: str
    game_cnt: int
    avg_price_usd: float
    avg_positive_rate: float
    avg_owners_mid: int
    avg_playtime_min: int


class GameDetail(BaseModel):
    appid: int
    name: str
    header_image: str | None
    release_date: str | None
    release_year: int | None
    price_usd: float
    price_bucket: str
    genres: list[str]
    developer: str | None
    publisher: str | None
    owners_low: int | None
    owners_high: int | None
    owners_mid: int | None
    peak_ccu: int | None
    review_cnt: int
    positive_cnt: int
    positive_rate: float | None
    avg_playtime_min: int | None
    median_playtime_min: int | None
    metacritic_score: int | None
    required_age: int | None
    dlc_count: int | None
    achievements: int | None
    num_languages: int | None
    platforms: list[str]
    cluster: GameCluster | None
    hot_pred: GameHotPred | None
    sentiment: GameSentiment | None
    peers: GamePeers | None


class ReviewTrendItem(BaseModel):
    month: str = Field(description="YYYY-MM（UTC）")
    review_cnt: int
    positive_cnt: int
    positive_rate: float | None


class PricePoint(BaseModel):
    date: str = Field(description="YYYY-MM-DD")
    price_usd: float
