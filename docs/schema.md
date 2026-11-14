# 数据表契约（schema）

> **维护：DJQuiller；Review：Mili**。本文件是全部表结构的唯一权威来源。修改流程：PR 中同时提交 `storage/migrations/V{n}__描述.sql`，经 Mili Review 后合并，合并后才在主库执行迁移并更新 `storage/sample/`。
>
> 状态：**草案**。表名与粒度已与接口契约对齐；字段类型与完整字段待补全（标 `TODO` 处）。

## 全局口径

| 口径 | 约定 |
|---|---|
| 货币 | 统一美元（USD），存 `DECIMAL(10,2)`；免费游戏价格为 `0` |
| 价格区间 `price_bucket` | `free` / `lt10` / `10_30` / `30_60` / `ge60` |
| 发行年份 `release_year` | 取正式发行日期的年份；未发行/日期缺失的游戏不进 `ads` |
| 类型 `genre` | 取 Steam 官方 genres；一款游戏有多个类型时，在按类型统计的表里**每个类型各计一次** |
| 好评率 | `positive / (positive + negative)`，评论总数 < 10 的游戏不参与好评率统计 |
| 拥有者 | SteamSpy 区间估算取中值 |
| 时间 | 一律存 UTC `DATETIME`；活跃时段热力图按 UTC 统计并在前端注明 |
| 字符集 | 库、表、列及客户端连接一律使用 `utf8mb4`，排序规则 `utf8mb4_0900_ai_ci`；禁止使用 `utf8`（即 `utf8mb3`），否则评论中的 emoji 会写入失败。建库：`CREATE DATABASE … CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci`；建表末尾显式写 `DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci`；连接串带 `charset=utf8mb4`；`mysqldump` 导出、导入时都加 `--default-character-set=utf8mb4` |

## 筛选维度约定

大屏的全局筛选为 **年份 / 类型 / 价格区间**。凡需响应筛选的 `ads_*` 表，必须保留 `release_year`、`genre`、`price_bucket` 三列作为聚合粒度，后端用 `WHERE` 过滤后再 `SUM … GROUP BY` 小表汇总。不响应筛选的表在下方标注"全局"。

## dwd 层（明细）

| 表 | 粒度 | 关键字段 |
|---|---|---|
| `dwd_game` | 一款游戏一行 | `appid` PK, `name`, `release_date`, `release_year`, `price_usd`, `price_bucket`, `owners_mid`, `positive`, `negative`, `avg_playtime_min`, `developer`, `publisher` TODO |
| `dwd_game_genre` | 游戏 × 类型 | `appid`, `genre` |
| `dwd_review` | 一条评论一行 | `review_id` PK, `appid`, `language`, `voted_up`, `playtime_at_review_min`, `timestamp_created` TODO |
| `dwd_ccu_snapshot` | 游戏 × 采集时刻 | `appid`, `snapshot_at`, `player_count` |
| `dwd_price_history` | 游戏 × 采集日期 | `appid`, `snapshot_date`, `price_usd`（详情页价格历史；仅增量采集后有数据） |

## ads 层（聚合 / 模型结果）

| 表 | 粒度 | 对应接口（见 `docs/api.md`） |
|---|---|---|
| `ads_kpi_overview` | 全局，单行 | `/overview/kpi` |
| `ads_yearly_release` | 年 × 类型 × 价格区间 → 发行量、价格合计 | `/trend/yearly` |
| `ads_genre_heat` | 年 × 类型 × 价格区间 → 游戏数、拥有者合计、评论数 | `/trend/genres` |
| `ads_price_rating` | 年 × 类型 × 价格区间 → 好评率分位数（箱线图五数） TODO：分位数无法跨组再汇总，需确认按筛选组合预计算或后端读 `dwd` | `/trend/price-rating` |
| `ads_top_sellers` | 游戏一行（带三筛选维度） → 拥有者、最新在线 | `/rank/top-sellers` |
| `ads_ccu_latest` | 全局，Top N 游戏最新快照 | `/rank/online-live` |
| `ads_game_cluster` | 游戏一行 → `cluster_id`, `cluster_label`, 二维坐标 `x`/`y` | `/cluster/games` |
| `ads_rating_dist` | 年 × 类型 × 价格区间 × 好评率分箱 → 游戏数 | `/ecosystem/rating-dist` |
| `ads_review_lang` | 年 × 类型 × 价格区间 × 语言 → 评论数 | `/ecosystem/review-languages` |
| `ads_playtime_dist` | 年 × 类型 × 价格区间 × 时长分箱 → 评论数 | `/ecosystem/playtime-dist` |
| `ads_review_heatmap` | 年 × 类型 × 价格区间 × 星期 × 小时 → 评论数 | `/ecosystem/activity-heatmap` |
| `ads_game_review_trend` | 游戏 × 月 → 评论数、好评数 | `/games/{appid}/reviews-trend` |
| `ads_hot_pred` | 游戏一行 → 热销预测概率、标签 | 详情页 |
| `ads_model_metrics` | 模型 × 指标 → 值（RF vs LR 对比） | 答辩展示 |
| `ads_review_sentiment` | 游戏一行 → 情感正向占比 | 详情页 |
| `ads_meta` | 键值 → 数据更新时间、各表行数 | `/meta/updated-at` |
