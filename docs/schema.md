# 数据表契约（schema）

> **维护方：数据组**。本文件是全部表结构的唯一权威来源。修改流程：PR 中同时提交 `storage/migrations/V{n}__描述.sql`，由可视化组 Review 后合并，合并后才在主库执行迁移并更新 `storage/sample/`。
>
> 状态：**草案 v0.2**。表名与粒度已与可视化组对齐；字段类型与完整字段待数据组补全（标 `TODO` 处）。目前尚未建表，本次修订不需要迁移脚本。
>
> v0.2 变更（M2 阶段由可视化组暂代数据组修订，待数据组成员 Review）：类型维度加 `__ALL__` 汇总行，避免多类型游戏重复计数；游戏粒度表通过 `dwd_game_genre` 筛选类型；删除 `ads_price_rating`，箱线图改由 1% 分箱的 `ads_rating_dist` 推算；注明随快照刷新的表。

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

可视化组的全局筛选为 **年份 / 类型 / 价格区间**。凡需响应筛选的 `ads_*` 表，必须保留 `release_year`、`genre`、`price_bucket` 三列作为聚合粒度，后端用 `WHERE` 过滤后再 `SUM … GROUP BY` 小表汇总。不响应筛选的表在下方标注"全局"。

一款游戏只属于一个年份、一个价格区间，所以这两个维度可以直接求和；但一款游戏可以属于多个类型，直接对 `genre` 求和会重复计数。因此分两类处理：

| 表的类型 | 做法 | 后端查询 |
|---|---|---|
| **聚合表**（带 `genre` 列） | 除了每个类型各一行，再预计算一组 `genre = '__ALL__'` 的汇总行，其中每款游戏、每条评论只计一次 | 没选类型：`WHERE genre = '__ALL__'`；选了类型：`WHERE genre = :genre`。之后再按年份、价格区间过滤并 `SUM` |
| **游戏粒度表**（一款游戏一行，不带 `genre` 列） | 只保留 `release_year`、`price_bucket` | 选了类型时，加条件 `EXISTS (SELECT 1 FROM dwd_game_genre g WHERE g.appid = t.appid AND g.genre = :genre)` |

`ads_genre_heat` 本身就是按类型展示，不设 `__ALL__` 行。`dwd_game_genre` 建联合主键 `(appid, genre)` 和索引 `(genre, appid)`。

## 库划分

| 库 | 层 | 访问权限 |
|---|---|---|
| `steam_ods` | `ods_*` | 只有 `etl_writer` |
| `steam` | `dwd_*`、`ads_*` | `etl_writer` 读写；`api_reader` 对整个库只有 `SELECT` |

分成两个库，是因为 MySQL 不支持按表名前缀授权；分库后用库级授权，就能做到"后端只读 dwd/ads"，以后新增表也不用逐表补授权。建表语句在 `scripts/init_db.sql`，它是字段类型的权威来源，本文件只列关键字段。

## ods 层（原始）

| 表 | 来源 | 说明 |
|---|---|---|
| `ods_game_kaggle` | Kaggle 游戏集 `games.csv` | 40 列原样落库（列名转为 snake_case），PK `app_id` |
| `ods_review_kaggle` | Kaggle 评论集 `reviews-*.parquet` | 只保留分析用字段，**不存评论原文和评论者 ID**；`src_shard` 记录来源分片，便于按分片重跑；PK `review_id` |
| `ods_ccu_snapshot` | `GetNumberOfCurrentPlayers`，每小时一轮 | 游戏 × 整点，PK `(appid, snapshot_at)`。`snapshot_at`（UTC，本轮开始时刻向下取整到整点）、`fetched_at`（UTC，实际请求时刻）、`http_status`、`attempts`、`raw_body`（响应正文原样）、`error`、`player_count`。**失败的请求也留一行**（`player_count` 为 NULL），用于统计哪些 appid 取不到；同一小时重跑只覆盖不新增，已成功的行不会被失败结果覆盖 |

## dwd 层（明细）

| 表 | 粒度 | 关键字段 |
|---|---|---|
| `dwd_game` | 一款游戏一行 | `appid` PK, `name`, `release_date`, `release_year`, `price_usd`, `price_bucket`, `owners_low`/`owners_high`/`owners_mid`, `peak_ccu`, `positive`, `negative`, `avg_playtime_min`, `median_playtime_min`, `developer`, `publisher`, `header_image`；热销预测用的发行前特征：`required_age`, `dlc_count`, `achievements`, `num_languages`, `on_windows`/`on_mac`/`on_linux`, `metacritic_score`。索引 `(release_year, price_bucket)` |
| `dwd_game_genre` | 游戏 × 类型 | `appid`, `genre` |
| `dwd_review` | 一条评论一行 | PK `(appid, review_id)`，聚簇主键让同一游戏的评论物理相邻；`language`, `voted_up`, `playtime_at_review_min`, `timestamp_created`（UTC） |
| `dwd_ccu_snapshot` | 游戏 × 采集时刻 | PK `(appid, snapshot_at)`，索引 `(snapshot_at)`；`snapshot_at`（UTC 整点，与 `ods_ccu_snapshot` 同口径）、`player_count`（非空）。只含取到人数的行；同一小时重跑覆盖，不产生重复行。只覆盖 `dwd_ccu_watchlist` 里的游戏 |
| `dwd_ccu_watchlist` | 采集名单，一款游戏一行 | `appid` PK, `peak_ccu_rank`、`owners_rank`（在各自前 500 里的名次，没进为 NULL）, `refreshed_at`（UTC）。名单 = `dwd_game` 中 `peak_ccu` 前 500 ∪ `owners_mid` 前 500；并列时的次序：`peak_ccu` 榜按 `peak_ccu` 降序 → `appid` 升序，`owners_mid` 榜按 `owners_mid` 降序 → `peak_ccu` 降序 → `appid` 升序。每天整表重建一次 |
| `dwd_price_history` | 游戏 × 采集日期 | `appid`, `snapshot_date`, `price_usd`（详情页价格历史；仅增量采集后有数据） |

## ads 层（聚合 / 模型结果）

"表类型"列：**聚合**表含 `__ALL__` 汇总行，**游戏**表按 `dwd_game_genre` 筛选类型，**全局**表不响应筛选。"刷新"列默认是随离线流水线刷新；标"每小时"的表由定时任务在写入在线人数快照后一并刷新。

| 表 | 表类型 | 粒度 | 刷新 | 对应接口（见 `docs/api.md`） |
|---|---|---|---|---|
| `ads_kpi_overview` | 全局 | 单行：游戏总数、评论总数、估算玩家总量、实时在线峰值 | 每小时（在线峰值） | `/overview/kpi` |
| `ads_yearly_release` | 聚合 | 年 × 类型 × 价格区间 → 发行量、价格合计（均价 = 价格合计 ÷ 发行量） | | `/trend/yearly` |
| `ads_genre_heat` | 聚合（无 `__ALL__`） | 年 × 类型 × 价格区间 → 游戏数、拥有者合计、评论数 | | `/trend/genres` |
| `ads_top_sellers` | 游戏 | 游戏一行（带 `release_year`、`price_bucket`） → 拥有者、最新在线人数 | 每小时（在线人数） | `/rank/top-sellers` |
| `ads_ccu_latest` | 全局 | Top N 游戏的最新快照 | 每小时 | `/rank/online-live` |
| `ads_game_cluster` | 游戏 | 游戏一行（带 `release_year`、`price_bucket`） → `cluster_id`, `cluster_label`, 二维坐标 `x`/`y` | | `/cluster/games` |
| `ads_rating_dist` | 聚合 | 年 × 类型 × 价格区间 × 好评率分箱 → 游戏数。分箱宽度 **1%**（`rating_bin` 取 0–99，好评率 100% 归入 99） | | `/ecosystem/rating-dist`、`/trend/price-rating` |
| `ads_review_lang` | 聚合 | 年 × 类型 × 价格区间 × 语言 → 评论数 | | `/ecosystem/review-languages` |
| `ads_playtime_dist` | 聚合 | 年 × 类型 × 价格区间 × 时长分箱 → 评论数 | | `/ecosystem/playtime-dist` |
| `ads_review_heatmap` | 聚合 | 年 × 类型 × 价格区间 × 星期 × 小时 → 评论数 | | `/ecosystem/activity-heatmap` |
| `ads_game_review_trend` | 全局 | 游戏 × 月 → 评论数、好评数 | | `/games/{appid}/reviews-trend` |
| `ads_hot_pred` | 全局 | 游戏一行 → 热销预测概率、标签 | | `/games/{appid}` |
| `ads_model_metrics` | 全局 | 模型 × 指标 → 值（RF vs LR 对比） | | 答辩展示 |
| `ads_review_sentiment` | 全局 | 游戏一行 → 情感正向占比 | | `/games/{appid}` |
| `ads_meta` | 全局 | 键值 → 数据更新时间、各表行数 | 每次刷新后 | `/meta/updated-at` |

**箱线图怎么从分箱推算**：`ads_rating_dist` 的分箱计数可以直接相加。后端按筛选条件 `SUM(game_cnt) … GROUP BY price_bucket, rating_bin` 后，在每个价格区间内按 `rating_bin` 累加，累计数第一次达到总数的 0%、25%、50%、75%、100% 时对应的分箱，就是箱线图的五数，精度为 1 个百分点。分位数本身不能跨组相加，所以不预存分位数，只预存分箱。`/ecosystem/rating-dist` 读同一张表，按 5% 或 10% 合并分箱后再展示。
