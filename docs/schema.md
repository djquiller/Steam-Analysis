# 数据表契约（schema）

> **维护方：数据组**。本文件是全部表结构的唯一权威来源。修改流程：PR 中同时提交 `storage/migrations/V{n}__描述.sql`，由可视化组 Review 后合并，合并后才在主库执行迁移并更新 `storage/sample/`。
>
> 状态：**草案 v0.3**。全部 `ads_*` 表的字段、类型、主键和口径已补全，建表语句已并入 `scripts/init_db.sql`。`ads` 表是首次建表（此前库里没有），语句全部是 `CREATE TABLE IF NOT EXISTS`，所以本次不另附迁移脚本；此后再改 `ads` 字段，照常附 `storage/migrations/V{n}__描述.sql`。
>
> v0.3 变更（由可视化组暂代数据组修订，待数据组成员 Review）：补全 15 张 `ads` 表的字段；写明价格区间的边界；`ads_genre_heat` 增加好评数，`ads_review_lang` 增加好评数；`ads_top_sellers` 收录全部有发行年份的游戏；`/meta/filters` 改读 `ads_yearly_release`。
>
> v0.2 变更（M2 阶段由可视化组暂代数据组修订，待数据组成员 Review）：类型维度加 `__ALL__` 汇总行，避免多类型游戏重复计数；游戏粒度表通过 `dwd_game_genre` 筛选类型；删除 `ads_price_rating`，箱线图改由 1% 分箱的 `ads_rating_dist` 推算；注明随快照刷新的表。

## 全局口径

| 口径 | 约定 |
|---|---|
| 货币 | 统一美元（USD），存 `DECIMAL(10,2)`；免费游戏价格为 `0` |
| 价格区间 `price_bucket` | `free`（价格 = 0）/ `lt10`（0 < 价格 < 10）/ `10_30`（10 ≤ 价格 < 30）/ `30_60`（30 ≤ 价格 < 60）/ `ge60`（价格 ≥ 60），单位美元 |
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

## dwd 层（明细）

| 表 | 粒度 | 关键字段 |
|---|---|---|
| `dwd_game` | 一款游戏一行 | `appid` PK, `name`, `release_date`, `release_year`, `price_usd`, `price_bucket`, `owners_low`/`owners_high`/`owners_mid`, `peak_ccu`, `positive`, `negative`, `avg_playtime_min`, `median_playtime_min`, `developer`, `publisher`, `header_image`；热销预测用的发行前特征：`required_age`, `dlc_count`, `achievements`, `num_languages`, `on_windows`/`on_mac`/`on_linux`, `metacritic_score`。索引 `(release_year, price_bucket)` |
| `dwd_game_genre` | 游戏 × 类型 | `appid`, `genre` |
| `dwd_review` | 一条评论一行 | PK `(appid, review_id)`，聚簇主键让同一游戏的评论物理相邻；`language`, `voted_up`, `playtime_at_review_min`, `timestamp_created`（UTC） |
| `dwd_ccu_snapshot` | 游戏 × 采集时刻 | `appid`, `snapshot_at`, `player_count` |
| `dwd_price_history` | 游戏 × 采集日期 | `appid`, `snapshot_date`, `price_usd`（详情页价格历史；仅增量采集后有数据） |

## ads 层（聚合 / 模型结果）

"表类型"列：**聚合**表含 `__ALL__` 汇总行，**游戏**表按 `dwd_game_genre` 筛选类型，**全局**表不响应筛选。"刷新"列默认是随离线流水线刷新；标"每小时"的表由定时任务在写入在线人数快照后一并刷新。"数据来自"列说明这张表靠哪些明细表算出来。

| 表 | 表类型 | 粒度 | 刷新 | 数据来自 | 对应接口（见 `docs/api.md`） |
|---|---|---|---|---|---|
| `ads_kpi_overview` | 全局 | 单行：游戏总数、评论总数、估算玩家总量、实时在线峰值 | 每小时（在线峰值） | 游戏表、评论表、在线快照 | `/overview/kpi` |
| `ads_yearly_release` | 聚合 | 年 × 类型 × 价格区间 → 发行量、价格合计（均价 = 价格合计 ÷ 发行量） | | 游戏表 | `/trend/yearly`、`/meta/filters` |
| `ads_genre_heat` | 聚合（无 `__ALL__`） | 年 × 类型 × 价格区间 → 游戏数、拥有者合计、评论数、好评数 | | 游戏表 | `/trend/genres` |
| `ads_top_sellers` | 游戏 | 游戏一行（带 `release_year`、`price_bucket`） → 拥有者、最新在线人数 | 每小时（在线人数） | 游戏表、在线快照 | `/rank/top-sellers` |
| `ads_ccu_latest` | 全局 | Top 100 游戏的最新快照 | 每小时 | 在线快照 | `/rank/online-live` |
| `ads_game_cluster` | 游戏 | 游戏一行（带 `release_year`、`price_bucket`） → `cluster_id`, `cluster_label`, 二维坐标 `x`/`y` | | 聚类模型 | `/cluster/games`、`/games/{appid}` |
| `ads_rating_dist` | 聚合 | 年 × 类型 × 价格区间 × 好评率分箱 → 游戏数。分箱宽度 **1%**（`rating_bin` 取 0–99，好评率 100% 归入 99） | | 游戏表 | `/ecosystem/rating-dist`、`/trend/price-rating` |
| `ads_review_lang` | 聚合 | 年 × 类型 × 价格区间 × 语言 → 评论数、好评数 | | 评论表 | `/ecosystem/review-languages` |
| `ads_playtime_dist` | 聚合 | 年 × 类型 × 价格区间 × 时长分箱 → 评论数 | | 评论表 | `/ecosystem/playtime-dist` |
| `ads_review_heatmap` | 聚合 | 年 × 类型 × 价格区间 × 星期 × 小时 → 评论数 | | 评论表 | `/ecosystem/activity-heatmap` |
| `ads_game_review_trend` | 全局 | 游戏 × 月 → 评论数、好评数 | | 评论表 | `/games/{appid}/reviews-trend` |
| `ads_hot_pred` | 全局 | 游戏一行 → 热销预测概率、标签 | | 热销预测模型 | `/games/{appid}` |
| `ads_model_metrics` | 全局 | 模型 × 指标 → 值（RF vs LR 对比） | | 各模型 | 无接口，答辩展示 |
| `ads_review_sentiment` | 全局 | 游戏一行 → 情感正向占比（存正向条数与样本条数） | | 情感模型 | `/games/{appid}` |
| `ads_meta` | 全局 | 键值 → 数据更新时间、各表行数 | 每次刷新后 | 各脚本 | `/meta/updated-at` |

**箱线图怎么从分箱推算**：`ads_rating_dist` 的分箱计数可以直接相加。后端按筛选条件 `SUM(game_cnt) … GROUP BY price_bucket, rating_bin` 后，在每个价格区间内按 `rating_bin` 累加，累计数第一次达到总数的 0%、25%、50%、75%、100% 时对应的分箱，就是箱线图的五数，精度为 1 个百分点。分位数本身不能跨组相加，所以不预存分位数，只预存分箱。`/ecosystem/rating-dist` 读同一张表，按 5% 或 10% 合并分箱后再展示。

### ads 通用约定

- **进入 `ads` 的游戏**：`dwd_game` 中 `release_year` 不为空的游戏。评论类的表只统计这些游戏的评论；评论的 `appid` 在 `dwd_game` 里找不到，或游戏没有发行年份的，不进这些表。
- **三个维度列**在所有聚合表里类型相同，并排在主键最前面：

  | 字段 | 类型 | 说明 |
  |---|---|---|
  | `release_year` | `SMALLINT NOT NULL` | **游戏的**发行年份。评论类的表里也是所评游戏的发行年份，不是评论发表的年份 |
  | `genre` | `VARCHAR(64) NOT NULL` | Steam 官方类型名，或保留值 `__ALL__` |
  | `price_bucket` | `VARCHAR(8) NOT NULL` | 五档之一，见"全局口径" |

- **`__ALL__` 行**：每款游戏（每条评论）只计一次，并且**包含没有任何类型的游戏**。所以 `__ALL__` 行的数不等于各类型行相加，也不等于"至少有一个类型的游戏数"。
- **只存可加的量**：聚合表只存计数（`*_cnt`）和合计（`*_sum`），后端过滤后直接 `SUM`。均价、好评率、占比、分位数都由后端用这些量现算，表里不存。游戏粒度的表一款游戏一行，不会再汇总，可以存比率。
- **稀疏存储**：某个维度组合下没有游戏（评论）就没有这一行，读取方按 0 处理。
- **时间列**一律 UTC `DATETIME`。
- 所有表 `ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci`。建表语句在 `scripts/init_db.sql`，与本节不一致时以本节为准并修正脚本。

下面各表的"可空"列：空着表示 `NOT NULL`。

### `ads_kpi_overview`（全局，单行）

主键 `id`，固定只有 `id = 1` 一行。不同来源的列由不同脚本更新，各自只更新自己的列。

| 字段 | 类型 | 可空 | 口径 / 单位 |
|---|---|---|---|
| `id` | `TINYINT UNSIGNED` | | 固定为 1 |
| `game_cnt` | `INT UNSIGNED` | | 游戏总数（款）：进入 `ads` 的游戏数，等于 `ads_yearly_release` 中 `__ALL__` 行的 `game_cnt` 之和 |
| `review_cnt` | `BIGINT UNSIGNED` | 可空 | 评论总数（条）：`dwd_review` 的行数。评论侧聚合写入之前为 `NULL` |
| `owners_total` | `BIGINT UNSIGNED` | | 估算玩家总量（份）：各游戏 `owners_mid` 之和。同一名玩家拥有多款游戏会被计多次，所以单位是"游戏拥有份数"，不是去重后的人数 |
| `online_peak_24h` | `INT UNSIGNED` | 可空 | 实时在线峰值（人）：最近 24 小时内，各采集时刻"采集名单内游戏的在线人数之和"的最大值。只覆盖采集名单内的游戏（约 600–800 款）。没有快照时为 `NULL` |
| `online_peak_at` | `DATETIME` | 可空 | 上述峰值出现的采集时刻（UTC） |
| `updated_at` | `DATETIME` | | 本行最近一次被更新的时间（UTC） |

### `ads_yearly_release`（聚合）

主键 `(release_year, genre, price_bucket)`。

| 字段 | 类型 | 可空 | 口径 / 单位 |
|---|---|---|---|
| `release_year`, `genre`, `price_bucket` | 见通用约定 | | 含 `__ALL__` 行 |
| `game_cnt` | `INT UNSIGNED` | | 发行量（款） |
| `price_sum` | `DECIMAL(14,2)` | | 这些游戏的 `price_usd` 之和（美元），免费游戏按 0 计入 |

均价 = `SUM(price_sum) ÷ SUM(game_cnt)`，含免费游戏。只想看付费游戏的均价，就在筛选里去掉 `free` 档。

### `ads_genre_heat`（聚合，无 `__ALL__`）

主键 `(release_year, genre, price_bucket)`。只有各类型的行；没有类型的游戏不出现在这张表里。

| 字段 | 类型 | 可空 | 口径 / 单位 |
|---|---|---|---|
| `release_year`, `genre`, `price_bucket` | 见通用约定 | | 不含 `__ALL__` 行 |
| `game_cnt` | `INT UNSIGNED` | | 该类型的游戏数（款）。一款游戏有多个类型时在每个类型下各计一次 |
| `owners_sum` | `BIGINT UNSIGNED` | | 这些游戏的 `owners_mid` 之和（份） |
| `review_cnt` | `BIGINT UNSIGNED` | | 这些游戏的 `positive + negative` 之和（条）。取自游戏集里 Steam 官方的好评、差评总数，不是 `dwd_review` 的行数 |
| `positive_cnt` | `BIGINT UNSIGNED` | | 这些游戏的 `positive` 之和（条）。`positive_cnt ÷ review_cnt` 是按评论计的好评占比，不是各游戏好评率的平均 |

### `ads_top_sellers`（游戏）

主键 `appid`。收录全部进入 `ads` 的游戏，这样任意筛选组合下的 Top N 都是精确的。索引：`(owners_mid, review_cnt)`、`(ccu_latest)`、`(release_year, price_bucket)`。

| 字段 | 类型 | 可空 | 口径 / 单位 |
|---|---|---|---|
| `appid` | `INT UNSIGNED` | | |
| `name` | `VARCHAR(512)` | | |
| `release_year` | `SMALLINT` | | |
| `price_bucket` | `VARCHAR(8)` | | |
| `price_usd` | `DECIMAL(10,2)` | | 美元 |
| `owners_mid` | `INT UNSIGNED` | 可空 | 拥有者（份），SteamSpy 区间估算中值 |
| `review_cnt` | `INT UNSIGNED` | | `positive + negative`（条） |
| `positive_cnt` | `INT UNSIGNED` | | `positive`（条）。好评率 = `positive_cnt ÷ review_cnt`，`review_cnt < 10` 时不展示 |
| `peak_ccu` | `INT UNSIGNED` | 可空 | 历史峰值在线（人），取自游戏集 |
| `ccu_latest` | `INT UNSIGNED` | 可空 | 最新在线人数（人）：`dwd_ccu_snapshot` 中最新一个采集时刻的 `player_count`。该时刻没有采到这款游戏则为 `NULL` |
| `ccu_at` | `DATETIME` | 可空 | `ccu_latest` 对应的采集时刻（UTC） |

排序口径：按拥有者排序时用 `owners_mid DESC, review_cnt DESC, appid ASC`。`owners_mid` 是区间中值，只有十几个取值，同档的游戏很多，所以用评论数做第二排序键。按在线人数排序时用 `ccu_latest DESC, appid ASC`，只取 `ccu_latest` 不为空的行。

`ccu_latest`、`ccu_at` 两列由定时任务每小时更新；离线流水线重建这张表时，会从 `dwd_ccu_snapshot` 重新取最新快照填回这两列。

### `ads_ccu_latest`（全局）

主键 `appid`。最新一个采集时刻在线人数最高的 100 款游戏，每小时整表重写。

| 字段 | 类型 | 可空 | 口径 / 单位 |
|---|---|---|---|
| `appid` | `INT UNSIGNED` | | |
| `name` | `VARCHAR(512)` | | |
| `player_count` | `INT UNSIGNED` | | 最新采集时刻的在线人数（人） |
| `player_count_prev` | `INT UNSIGNED` | 可空 | 上一个采集时刻的在线人数（人），供榜单显示升降；上一时刻没有采到则为 `NULL` |
| `snapshot_at` | `DATETIME` | | 最新采集时刻（UTC），全表相同 |

### `ads_game_cluster`（游戏）

主键 `appid`。只收录参与聚类的游戏：进入 `ads`，且评论总数 ≥ 10（好评率是聚类特征之一）。索引：`(release_year, price_bucket)`、`(cluster_id)`、`(sample_key)`。

| 字段 | 类型 | 可空 | 口径 / 单位 |
|---|---|---|---|
| `appid` | `INT UNSIGNED` | | |
| `name` | `VARCHAR(512)` | | |
| `release_year` | `SMALLINT` | | |
| `price_bucket` | `VARCHAR(8)` | | |
| `cluster_id` | `TINYINT UNSIGNED` | | 簇编号，从 0 开始 |
| `cluster_label` | `VARCHAR(32)` | | 簇的业务标签，如"爆款大作" |
| `x`, `y` | `FLOAT` | | PCA 降到二维后的坐标，无单位 |
| `price_usd` | `DECIMAL(10,2)` | | 聚类特征的原始值：价格（美元） |
| `positive_rate` | `DECIMAL(5,4)` | | 聚类特征的原始值：好评率，0–1 |
| `owners_mid` | `INT UNSIGNED` | | 聚类特征的原始值：拥有者（份） |
| `avg_playtime_min` | `INT UNSIGNED` | | 聚类特征的原始值：平均游玩时长（分钟） |
| `sample_key` | `INT UNSIGNED` | | `CRC32(appid)`。散点图只画一部分点时，后端 `ORDER BY sample_key LIMIT n`，得到一份固定的均匀随机子集 |

四个特征原始值用于散点提示框，也用于详情页的同类对比（后端对同一个 `cluster_id` 求平均）。

### `ads_rating_dist`（聚合）

主键 `(release_year, genre, price_bucket, rating_bin)`。只统计评论总数 ≥ 10 的游戏。

| 字段 | 类型 | 可空 | 口径 / 单位 |
|---|---|---|---|
| `release_year`, `genre`, `price_bucket` | 见通用约定 | | 含 `__ALL__` 行 |
| `rating_bin` | `TINYINT UNSIGNED` | | 好评率分箱，0–99。`rating_bin = LEAST(FLOOR(100 × positive ÷ (positive + negative)), 99)`，即分箱 `n` 表示好评率在 `[n%, (n+1)%)`，100% 归入 99 |
| `game_cnt` | `INT UNSIGNED` | | 落在该分箱的游戏数（款） |

### `ads_review_lang`（聚合）

主键 `(release_year, genre, price_bucket, language)`。

| 字段 | 类型 | 可空 | 口径 / 单位 |
|---|---|---|---|
| `release_year`, `genre`, `price_bucket` | 见通用约定 | | 含 `__ALL__` 行 |
| `language` | `VARCHAR(32)` | | 评论语言，取 `dwd_review.language` 原值（Steam 的语言代码，如 `english`、`schinese`） |
| `review_cnt` | `BIGINT UNSIGNED` | | 评论数（条） |
| `positive_cnt` | `BIGINT UNSIGNED` | | 其中 `voted_up = 1` 的评论数（条） |

### `ads_playtime_dist`（聚合）

主键 `(release_year, genre, price_bucket, playtime_bin)`。按 `dwd_review.playtime_at_review_min`（写评论时的累计游玩时长）分箱；该字段为空的评论不计入。

| 字段 | 类型 | 可空 | 口径 / 单位 |
|---|---|---|---|
| `release_year`, `genre`, `price_bucket` | 见通用约定 | | 含 `__ALL__` 行 |
| `playtime_bin` | `TINYINT UNSIGNED` | | 时长分箱编号 0–10，见下表 |
| `review_cnt` | `BIGINT UNSIGNED` | | 评论数（条） |

时长分箱（左闭右开，单位小时；括号里是对应的分钟数）：

| `playtime_bin` | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 区间（小时） | [0, 1) | [1, 2) | [2, 5) | [5, 10) | [10, 20) | [20, 50) | [50, 100) | [100, 200) | [200, 500) | [500, 1000) | ≥ 1000 |
| 下界（分钟） | 0 | 60 | 120 | 300 | 600 | 1200 | 3000 | 6000 | 12000 | 30000 | 60000 |

游玩时长跨越四个数量级，等宽分箱会把绝大多数评论挤进第一格，所以用近似对数的固定分箱。

### `ads_review_heatmap`（聚合）

主键 `(release_year, genre, price_bucket, weekday, hour)`。按 `dwd_review.timestamp_created`（UTC）统计。

| 字段 | 类型 | 可空 | 口径 / 单位 |
|---|---|---|---|
| `release_year`, `genre`, `price_bucket` | 见通用约定 | | 含 `__ALL__` 行 |
| `weekday` | `TINYINT UNSIGNED` | | 星期，0 = 周一 … 6 = 周日（MySQL `WEEKDAY()` 的取值），UTC |
| `hour` | `TINYINT UNSIGNED` | | 小时，0–23，UTC |
| `review_cnt` | `BIGINT UNSIGNED` | | 评论数（条） |

### `ads_game_review_trend`（全局）

主键 `(appid, month_start)`，同一款游戏的各月物理相邻，详情页按 `appid` 范围读取。

| 字段 | 类型 | 可空 | 口径 / 单位 |
|---|---|---|---|
| `appid` | `INT UNSIGNED` | | |
| `month_start` | `DATE` | | 评论发表月份的第一天（UTC），如 `2024-03-01` |
| `review_cnt` | `INT UNSIGNED` | | 该月评论数（条） |
| `positive_cnt` | `INT UNSIGNED` | | 该月 `voted_up = 1` 的评论数（条） |

没有评论的月份不存行。

### `ads_hot_pred`（全局）

主键 `appid`。每款参与建模的游戏一行，存最终选用的那个模型的预测结果。

| 字段 | 类型 | 可空 | 口径 / 单位 |
|---|---|---|---|
| `appid` | `INT UNSIGNED` | | |
| `hot_prob` | `DECIMAL(5,4)` | | 模型给出的热销概率，0–1 |
| `hot_pred` | `TINYINT(1)` | | 预测标签：1 = 预测为热销 |
| `hot_actual` | `TINYINT(1)` | | 实际标签：`owners_mid` 不低于全体游戏第 90 百分位记为 1（定义见 `analysis/CLAUDE.md`） |
| `is_test` | `TINYINT(1)` | | 1 = 这款游戏在测试集里（模型训练时没见过），0 = 在训练集里。详情页展示预测时据此注明 |
| `model_name` | `VARCHAR(32)` | | 产生这条预测的模型，取值与 `ads_model_metrics.model_name` 一致 |

### `ads_model_metrics`（全局）

主键 `(model_name, metric)`。没有对应接口，供答辩展示和模型报告引用。

| 字段 | 类型 | 可空 | 口径 / 单位 |
|---|---|---|---|
| `model_name` | `VARCHAR(32)` | | 模型标识，如 `hot_rf`、`hot_lr`、`sentiment_lr`、`cluster_kmeans` |
| `metric` | `VARCHAR(32)` | | 指标名，如 `accuracy`、`precision`、`recall`、`f1`、`auc`、`silhouette`、`positive_ratio`、`k` |
| `metric_value` | `DOUBLE` | | 指标值 |
| `updated_at` | `DATETIME` | | 写入时间（UTC） |

### `ads_review_sentiment`（全局）

主键 `appid`。只有抽到评论原文的游戏才有行。

| 字段 | 类型 | 可空 | 口径 / 单位 |
|---|---|---|---|
| `appid` | `INT UNSIGNED` | | |
| `sample_cnt` | `INT UNSIGNED` | | 参与打分的评论条数（条） |
| `positive_cnt` | `INT UNSIGNED` | | 其中判为正向的条数（条）。情感正向占比 = `positive_cnt ÷ sample_cnt` |
| `method` | `VARCHAR(16)` | | `model` = 情感模型打分；`voted_up` = 降级为直接统计 `voted_up` |

### `ads_meta`（全局）

主键 `meta_key`。各脚本只写自己负责的键（有则更新，无则插入），不清空整表。

| 字段 | 类型 | 可空 | 口径 / 单位 |
|---|---|---|---|
| `meta_key` | `VARCHAR(64)` | | 键，取值见下 |
| `meta_value` | `VARCHAR(255)` | | 值，一律存成字符串 |
| `updated_at` | `DATETIME` | | 这个键最近一次写入的时间（UTC） |

| 键 | 值 |
|---|---|
| `data_updated_at` | 离线流水线最近一次刷新完成的时间，UTC，格式 `YYYY-MM-DD HH:MM:SS` |
| `ccu_updated_at` | 定时任务最近一次刷新在线人数相关表的时间，格式同上 |
| `rows.<表名>` | 该表的行数，如 `rows.dwd_game`、`rows.ads_yearly_release`。由写这张表的脚本在写完后登记 |
