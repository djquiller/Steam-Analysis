# 接口契约（API）

> **维护：DJQuiller；Review：Mili**。本文件是后端接口的唯一权威来源；运行时以 FastAPI 自带 Swagger（`/docs`）为准，本文件随之同步。修改需发 PR，经 Mili Review 后合并。
>
> 状态：**草案 v0.3**。每个接口 `data` 的结构已补全，字段与 `docs/schema.md` v0.3 的 `ads` 表一一对应。老师尚未下发"标准数据契约"，下发后逐字段对齐并更新本文件。
>
> v0.3.1 变更：写明各错误码对应的 HTTP 状态码；新增 `GET /health`。16 个接口已在 `backend/` 实现，运行时 Swagger 见 `http://127.0.0.1:8000/docs`。
>
> v0.3 变更：补全各接口 `data` 的结构；`/meta/filters` 改读 `ads_yearly_release`；`/trend/genres` 不响应 `genre` 参数；`/rank/online-live`、`/cluster/games`、`/ecosystem/rating-dist`、`/ecosystem/review-languages` 增加可选参数；`/games/{appid}` 增加同类对比。
>
> v0.2 变更：价格筛选由 `price_min`/`price_max` 改为按档位多选的 `price_bucket`；`/trend/price-rating` 改读 `ads_rating_dist`；注明游戏粒度接口如何按类型筛选。

## 返回信封

```json
{ "code": 0, "msg": "ok", "data": {} }
```

| code | HTTP 状态码 | 含义 |
|---|---|---|
| `0` | 200 | 成功（含空结果：`data` 为空数组/空对象，前端显示空态） |
| `40001` | 400 | 参数错误（取值越界、类型不对、`genre` 不在 `/meta/filters` 里等），`msg` 写明是哪个参数 |
| `40401` | 404 | 资源不存在（如 appid 不存在、接口路径不存在） |
| `50001` | 500 | 数据库异常（连不上、查询出错），`msg` 不含 SQL 与连接信息，详情只记在后端日志 |

出错时 `data` 为 `null`。HTTP 状态码与 `code` 同时设置；前端 axios 拦截器在成功和失败两条分支里都读响应体的 `code` 与 `msg`。

另有 `GET /health`（不带 `/api/v1` 前缀、不查库）供部署时检查服务是否启动，返回 `{"code":0,"msg":"ok","data":{"status":"up"}}`。

## 全局筛选参数

所有标注"可筛选"的接口都接受以下查询参数，全部可选：

| 参数 | 类型 | 说明 |
|---|---|---|
| `year_start` / `year_end` | int | 发行年份闭区间 |
| `genre` | string | 单个类型名，取值见 `/meta/filters`；不传表示全部类型（后端读 `__ALL__` 汇总行，见 `docs/schema.md`"筛选维度约定"） |
| `price_bucket` | string | 价格区间，可多选，逗号分隔，如 `free,lt10`；取值 `free` / `lt10` / `10_30` / `30_60` / `ge60`，与表中的档位一一对应；不传表示全部 |

价格区间直接按档位筛选，不接受任意金额：表里只存了档位，任意金额（如 ≤ 20 美元）无法精确换算。非法取值返回 `40001`。

年份筛选的始终是**游戏的发行年份**。评论类接口（语言、时长、活跃时段）筛出的是"这些年份发行的游戏收到的评论"，不是"这些年份发表的评论"。

## 接口清单

前缀 `/api/v1`。数据来源表见 `docs/schema.md`。

| 接口 | 可筛选 | 用途 | 来源表 |
|---|---|---|---|
| `GET /meta/filters` | | 筛选项（年份范围、类型列表、价格区间） | `ads_yearly_release` |
| `GET /meta/updated-at` | | 数据更新时间 | `ads_meta` |
| `GET /overview/kpi` | | 游戏总数 / 评论总数 / 估算玩家总量 / 实时在线峰值 | `ads_kpi_overview` |
| `GET /trend/yearly` | ✓ | 历年发行量与均价 | `ads_yearly_release` |
| `GET /trend/genres` | ✓（不含 `genre`） | 类型热度 | `ads_genre_heat` |
| `GET /trend/price-rating` | ✓ | 价格区间 × 好评率箱线（由 1% 分箱推算五数） | `ads_rating_dist` |
| `GET /rank/top-sellers?metric=owners\|ccu&limit=10` | ✓ | 热销 Top10 | `ads_top_sellers`（筛类型时关联 `dwd_game_genre`） |
| `GET /rank/online-live?limit=20` | | 实时在线榜（前端 60 秒轮询） | `ads_ccu_latest` |
| `GET /cluster/games?limit=3000` | ✓ | 聚类散点 | `ads_game_cluster`（筛类型时关联 `dwd_game_genre`） |
| `GET /ecosystem/rating-dist?bin_width=5` | ✓ | 好评率分布 | `ads_rating_dist` |
| `GET /ecosystem/review-languages?limit=10` | ✓ | 评论语言分布 | `ads_review_lang` |
| `GET /ecosystem/playtime-dist` | ✓ | 游玩时长分布 | `ads_playtime_dist` |
| `GET /ecosystem/activity-heatmap` | ✓ | 星期 × 小时评论活跃度 | `ads_review_heatmap` |
| `GET /games/{appid}` | | 单款游戏详情（含预测、情感、聚类标签、同类对比） | `dwd_game`, `dwd_game_genre`, `ads_hot_pred`, `ads_review_sentiment`, `ads_game_cluster` |
| `GET /games/{appid}/reviews-trend` | | 评论量与好评率月度走势 | `ads_game_review_trend` |
| `GET /games/{appid}/price-history` | | 价格历史 | `dwd_price_history` |

`ads_model_metrics` 没有接口，只在答辩和模型报告里引用。

## `data` 结构

### 通用约定

| 项 | 约定 |
|---|---|
| 计数（`*_cnt`、`*_sum`、`owners_*`、`player_count`） | 整数。单位写在各字段说明里：款、条、份、人 |
| 金额 | 美元，数字，保留 2 位小数 |
| 比率（`*_rate`、`share`、`*_ratio`、`hot_prob`） | 0–1 的小数，保留 4 位。由后端用表里的计数现算；分母为 0 时返回 `null` |
| 好评率（按游戏） | `positive_cnt ÷ review_cnt`；`review_cnt < 10` 时返回 `null`（口径见 `docs/schema.md`） |
| 时间 | ISO 8601、UTC、带 `Z`，如 `"2026-11-12T08:00:00Z"`；日期为 `"YYYY-MM-DD"`，月份为 `"YYYY-MM"` |
| 尚无数据 | 对应字段返回 `null`（如还没有在线快照时的在线峰值），列表返回 `[]`。前端显示"—"或空态，不用假数据顶替 |
| 列表顺序 | 各接口写明了排序；前端按返回顺序画图 |

下面的示例里，游戏表能算出的接口用的是本机全量库的真实数字（2026-11-12）；依赖评论表、在线快照和模型的接口，相应的表还没有数据，示例数值只是示意，已逐个注明。

### `GET /meta/filters`

取值来自 `ads_yearly_release`：年份范围和各价格区间的游戏数读 `__ALL__` 行，类型列表读其余行。`genres` 按游戏数从多到少排序。全局筛选参数 `genre` 的合法取值就是这里的 `genres[].genre`。

| 字段 | 类型 | 说明 |
|---|---|---|
| `years.min` / `years.max` | int | 可选的发行年份范围 |
| `genres[].genre` | string | 类型名 |
| `genres[].game_cnt` | int | 该类型的游戏数（款） |
| `price_buckets[].key` | string | 档位取值，固定按 `free`、`lt10`、`10_30`、`30_60`、`ge60` 的顺序返回 |
| `price_buckets[].label` | string | 展示用文字 |
| `price_buckets[].game_cnt` | int | 该档位的游戏数（款） |

```json
{
  "years": { "min": 1997, "max": 2026 },
  "genres": [
    { "genre": "Indie", "game_cnt": 82883 },
    { "genre": "Casual", "game_cnt": 51677 }
  ],
  "price_buckets": [
    { "key": "free", "label": "免费", "game_cnt": 26659 },
    { "key": "lt10", "label": "$10 以下", "game_cnt": 86864 },
    { "key": "10_30", "label": "$10–30", "game_cnt": 11184 },
    { "key": "30_60", "label": "$30–60", "game_cnt": 738 },
    { "key": "ge60", "label": "$60 及以上", "game_cnt": 408 }
  ]
}
```

### `GET /meta/updated-at`

来自 `ads_meta`。

| 字段 | 类型 | 说明 |
|---|---|---|
| `data_updated_at` | string \| null | 键 `data_updated_at`：离线流水线最近一次刷新完成的时间 |
| `ccu_updated_at` | string \| null | 键 `ccu_updated_at`：在线人数最近一次刷新的时间；定时任务没跑过时为 `null` |
| `tables[].table` | string | 表名（键 `rows.<表名>` 去掉前缀） |
| `tables[].rows` | int | 该表行数 |
| `tables[].updated_at` | string | 这个行数是什么时候登记的 |

```json
{
  "data_updated_at": "2026-11-12T08:00:00Z",
  "ccu_updated_at": null,
  "tables": [
    { "table": "dwd_game", "rows": 125854, "updated_at": "2026-11-12T08:00:00Z" },
    { "table": "ads_top_sellers", "rows": 125853, "updated_at": "2026-11-12T08:00:00Z" }
  ]
}
```

### `GET /overview/kpi`

来自 `ads_kpi_overview` 的唯一一行。表里没有这一行时返回 `{}`。

| 字段 | 类型 | 说明 |
|---|---|---|
| `game_cnt` | int | 游戏总数（款） |
| `review_cnt` | int \| null | 评论总数（条）；评论侧聚合完成前为 `null` |
| `owners_total` | int | 估算玩家总量（份）：各游戏拥有者估算中值之和，同一玩家拥有多款会重复计 |
| `online_peak_24h` | int \| null | 实时在线峰值（人）：最近 24 小时采集名单内游戏在线人数之和的最大值；没有快照时为 `null` |
| `online_peak_at` | string \| null | 峰值出现的时刻 |
| `updated_at` | string | 这一行最近更新的时间 |

```json
{
  "game_cnt": 125853,
  "review_cnt": null,
  "owners_total": 10515020000,
  "online_peak_24h": null,
  "online_peak_at": null,
  "updated_at": "2026-11-12T08:00:00Z"
}
```

### `GET /trend/yearly`（可筛选）

来自 `ads_yearly_release`，按年份 `SUM` 后返回数组，年份从早到晚。筛选后没有游戏的年份不返回。

| 字段 | 类型 | 说明 |
|---|---|---|
| `year` | int | 发行年份 |
| `game_cnt` | int | 发行量（款），柱 |
| `price_sum` | number | 价格合计（美元） |
| `avg_price_usd` | number | 均价（美元）= `price_sum ÷ game_cnt`，含免费游戏，折线 |

```json
[
  { "year": 2024, "game_cnt": 20033, "price_sum": 101508.92, "avg_price_usd": 5.07 },
  { "year": 2025, "game_cnt": 24973, "price_sum": 126841.85, "avg_price_usd": 5.08 }
]
```

### `GET /trend/genres`（可筛选：年份、价格区间）

来自 `ads_genre_heat`，按类型 `SUM` 后返回数组，按 `game_cnt` 从多到少。**不响应 `genre` 参数**：树图要一直展示全部类型，选中的类型由前端高亮；传了 `genre` 也照常返回全部类型。

| 字段 | 类型 | 说明 |
|---|---|---|
| `genre` | string | 类型名 |
| `game_cnt` | int | 游戏数（款）；多类型游戏在每个类型下各计一次 |
| `owners_sum` | int | 拥有者合计（份） |
| `review_cnt` | int | 评论数（条），Steam 官方好评 + 差评总数 |
| `positive_cnt` | int | 好评数（条） |
| `positive_rate` | number \| null | 按评论计的好评占比 = `positive_cnt ÷ review_cnt` |

```json
[
  { "genre": "Indie", "game_cnt": 82883, "owners_sum": 4683355000, "review_cnt": 57768876, "positive_cnt": 51574692, "positive_rate": 0.8928 },
  { "genre": "Casual", "game_cnt": 51677, "owners_sum": 2003955000, "review_cnt": 19860177, "positive_cnt": 17505528, "positive_rate": 0.8814 }
]
```

### `GET /trend/price-rating`（可筛选）

来自 `ads_rating_dist`。后端按筛选条件 `SUM(game_cnt) … GROUP BY price_bucket, rating_bin`，再在每个价格区间内由累计分布读出五数。分位数 `p` 取"累计游戏数第一次达到 `ceil(p × 总数)`（至少为 1）时所在的分箱"。返回数组，按 `free`、`lt10`、`10_30`、`30_60`、`ge60` 的顺序；筛选后没有游戏的价格区间不返回。只统计评论总数 ≥ 10 的游戏。

| 字段 | 类型 | 说明 |
|---|---|---|
| `price_bucket` | string | 价格区间 |
| `game_cnt` | int | 参与统计的游戏数（款） |
| `min` / `q1` / `median` / `q3` / `max` | int | 好评率五数，单位 %。值是分箱下界：`78` 表示好评率在 78%–79% 之间，精度 1 个百分点；100% 归入 `99` |

```json
[
  { "price_bucket": "free", "game_cnt": 7384, "min": 12, "q1": 64, "median": 78, "q3": 88, "max": 99 },
  { "price_bucket": "lt10", "game_cnt": 42638, "min": 0, "q1": 67, "median": 81, "q3": 91, "max": 99 },
  { "price_bucket": "10_30", "game_cnt": 6186, "min": 0, "q1": 70, "median": 82, "q3": 91, "max": 99 },
  { "price_bucket": "30_60", "game_cnt": 303, "min": 20, "q1": 65, "median": 79, "q3": 89, "max": 99 },
  { "price_bucket": "ge60", "game_cnt": 151, "min": 0, "q1": 32, "median": 56, "q3": 77, "max": 99 }
]
```

### `GET /rank/top-sellers`（可筛选）

来自 `ads_top_sellers`；传了 `genre` 时加 `EXISTS` 关联 `dwd_game_genre`。

| 参数 | 类型 | 说明 |
|---|---|---|
| `metric` | string | `owners`（默认）：按 `owners_mid DESC, review_cnt DESC, appid ASC` 排序；`ccu`：按 `ccu_latest DESC, appid ASC` 排序，只返回有最新在线人数的游戏。其他取值返回 `40001` |
| `limit` | int | 返回条数，1–50，默认 10 |

返回数组，已按所选口径排好序。还没有在线快照时，`metric=ccu` 返回 `[]`。

| 字段 | 类型 | 说明 |
|---|---|---|
| `rank` | int | 名次，从 1 开始 |
| `appid` | int | 下钻到 `/game/:appid` 用 |
| `name` | string | 游戏名 |
| `release_year` | int | 发行年份 |
| `price_usd` | number | 价格（美元） |
| `owners_mid` | int \| null | 拥有者（份），SteamSpy 区间估算中值 |
| `ccu_latest` | int \| null | 最新在线人数（人） |
| `ccu_at` | string \| null | 最新在线人数的采集时刻 |
| `peak_ccu` | int \| null | 历史峰值在线（人） |
| `review_cnt` | int | 评论数（条） |
| `positive_rate` | number \| null | 好评率 |

```json
[
  { "rank": 1, "appid": 730, "name": "Counter-Strike 2", "release_year": 2012, "price_usd": 0.0, "owners_mid": 150000000, "ccu_latest": null, "ccu_at": null, "peak_ccu": 1013936, "review_cnt": 8815087, "positive_rate": 0.8669 },
  { "rank": 2, "appid": 578080, "name": "PUBG: BATTLEGROUNDS", "release_year": 2017, "price_usd": 0.0, "owners_mid": 150000000, "ccu_latest": null, "ccu_at": null, "peak_ccu": 314682, "review_cnt": 2557944, "positive_rate": 0.5944 }
]
```

### `GET /rank/online-live`

来自 `ads_ccu_latest`。`limit`：1–100，默认 20。

| 字段 | 类型 | 说明 |
|---|---|---|
| `snapshot_at` | string \| null | 这份榜单的采集时刻；表为空时为 `null` |
| `items[].rank` | int | 名次，按 `player_count` 从高到低 |
| `items[].appid` | int | |
| `items[].name` | string | |
| `items[].player_count` | int | 当前在线人数（人） |
| `items[].player_count_prev` | int \| null | 上一个采集时刻的在线人数（人），用来显示升降 |

```json
{
  "snapshot_at": "2026-11-20T12:00:00Z",
  "items": [
    { "rank": 1, "appid": 730, "name": "Counter-Strike 2", "player_count": 987654, "player_count_prev": 975310 }
  ]
}
```

（示意值，在线快照尚未开始采集。表为空时返回 `{ "snapshot_at": null, "items": [] }`。）

### `GET /cluster/games`（可筛选）

来自 `ads_game_cluster`；传了 `genre` 时加 `EXISTS` 关联 `dwd_game_genre`。`limit`：返回的散点上限，100–10000，默认 3000。符合筛选的游戏多于 `limit` 时，后端 `ORDER BY sample_key LIMIT :limit` 取一份固定的随机子集；`total` 和 `clusters` 始终按全部符合筛选的游戏统计。

| 字段 | 类型 | 说明 |
|---|---|---|
| `total` | int | 符合筛选的游戏数（款） |
| `clusters[].cluster_id` | int | 簇编号 |
| `clusters[].cluster_label` | string | 簇的业务标签，图例用 |
| `clusters[].game_cnt` | int | 该簇符合筛选的游戏数（款） |
| `points[].appid` | int | 下钻用 |
| `points[].name` | string | |
| `points[].cluster_id` | int | 决定颜色 |
| `points[].x` / `points[].y` | number | PCA 二维坐标，无单位 |
| `points[].price_usd` | number | 价格（美元） |
| `points[].positive_rate` | number | 好评率 |
| `points[].owners_mid` | int | 拥有者（份） |

```json
{
  "total": 56662,
  "clusters": [
    { "cluster_id": 0, "cluster_label": "小众精品", "game_cnt": 21034 }
  ],
  "points": [
    { "appid": 730, "name": "Counter-Strike 2", "cluster_id": 2, "x": 6.4132, "y": -0.8821, "price_usd": 0.0, "positive_rate": 0.8669, "owners_mid": 150000000 }
  ]
}
```

（`total` 是目前符合条件的游戏数，其余为示意值，聚类尚未运行。）

### `GET /ecosystem/rating-dist`（可筛选）

来自 `ads_rating_dist`，把 1% 分箱合并成 `bin_width` 宽的分箱。`bin_width`：`1`、`5`（默认）、`10`，其他取值返回 `40001`。只统计评论总数 ≥ 10 的游戏。`bins` 始终返回 `100 ÷ bin_width` 项（没有游戏的分箱 `game_cnt` 为 0），按 `bin_start` 从小到大。

| 字段 | 类型 | 说明 |
|---|---|---|
| `bin_width` | int | 分箱宽度，单位 % |
| `game_cnt` | int | 参与统计的游戏总数（款） |
| `bins[].bin_start` / `bins[].bin_end` | int | 分箱范围，单位 %，左闭右开；最后一箱含 100% |
| `bins[].game_cnt` | int | 该分箱的游戏数（款） |

```json
{
  "bin_width": 10,
  "game_cnt": 56662,
  "bins": [
    { "bin_start": 0, "bin_end": 10, "game_cnt": 80 },
    { "bin_start": 10, "bin_end": 20, "game_cnt": 280 },
    { "bin_start": 20, "bin_end": 30, "game_cnt": 711 },
    { "bin_start": 30, "bin_end": 40, "game_cnt": 1383 },
    { "bin_start": 40, "bin_end": 50, "game_cnt": 2320 },
    { "bin_start": 50, "bin_end": 60, "game_cnt": 4443 },
    { "bin_start": 60, "bin_end": 70, "game_cnt": 7010 },
    { "bin_start": 70, "bin_end": 80, "game_cnt": 10122 },
    { "bin_start": 80, "bin_end": 90, "game_cnt": 14022 },
    { "bin_start": 90, "bin_end": 100, "game_cnt": 16291 }
  ]
}
```

### `GET /ecosystem/review-languages`（可筛选）

来自 `ads_review_lang`，按语言 `SUM`。`limit`：单独列出的语言数，1–30，默认 10；其余语言合并成最后一项 `language = "other"`（没有其余语言时不返回这一项）。`items` 按 `review_cnt` 从多到少，`other` 固定排最后。

| 字段 | 类型 | 说明 |
|---|---|---|
| `review_cnt` | int | 符合筛选的评论总数（条） |
| `items[].language` | string | Steam 语言代码，如 `english`、`schinese`；或 `other` |
| `items[].review_cnt` | int | 评论数（条） |
| `items[].positive_cnt` | int | 好评数（条） |
| `items[].positive_rate` | number \| null | 好评占比 |
| `items[].share` | number | 占评论总数的比例 |

```json
{
  "review_cnt": 121000000,
  "items": [
    { "language": "english", "review_cnt": 54000000, "positive_cnt": 46000000, "positive_rate": 0.8519, "share": 0.4463 },
    { "language": "other", "review_cnt": 9000000, "positive_cnt": 7500000, "positive_rate": 0.8333, "share": 0.0744 }
  ]
}
```

（示意值，评论侧聚合尚未运行。）

### `GET /ecosystem/playtime-dist`（可筛选）

来自 `ads_playtime_dist`，按分箱 `SUM`。`bins` 始终返回全部 11 个分箱，按 `bin` 从小到大。统计的是"写评论时的累计游玩时长"，缺这个字段的评论不计入。

| 字段 | 类型 | 说明 |
|---|---|---|
| `review_cnt` | int | 参与统计的评论总数（条） |
| `bins[].bin` | int | 分箱编号 0–10，定义见 `docs/schema.md` 的 `ads_playtime_dist` |
| `bins[].min_hours` | int | 分箱下界（小时，含） |
| `bins[].max_hours` | int \| null | 分箱上界（小时，不含）；最后一箱为 `null`，表示 1000 小时及以上 |
| `bins[].review_cnt` | int | 评论数（条） |

```json
{
  "review_cnt": 120000000,
  "bins": [
    { "bin": 0, "min_hours": 0, "max_hours": 1, "review_cnt": 6000000 },
    { "bin": 10, "min_hours": 1000, "max_hours": null, "review_cnt": 3000000 }
  ]
}
```

（示意值，且只列了首尾两箱。）

### `GET /ecosystem/activity-heatmap`（可筛选）

来自 `ads_review_heatmap`，按星期和小时 `SUM`。`cells` 始终返回 7 × 24 = 168 项（没有评论的格子为 0），按 `weekday`、`hour` 从小到大。时间一律 UTC，图表标题注明。

| 字段 | 类型 | 说明 |
|---|---|---|
| `timezone` | string | 固定 `"UTC"` |
| `review_cnt` | int | 符合筛选的评论总数（条） |
| `max_cnt` | int | 各格子里最大的评论数（条），供色阶定上限 |
| `cells[].weekday` | int | 0 = 周一 … 6 = 周日 |
| `cells[].hour` | int | 0–23 |
| `cells[].review_cnt` | int | 评论数（条） |

```json
{
  "timezone": "UTC",
  "review_cnt": 121000000,
  "max_cnt": 960000,
  "cells": [
    { "weekday": 0, "hour": 0, "review_cnt": 610000 },
    { "weekday": 0, "hour": 1, "review_cnt": 598000 }
  ]
}
```

（示意值，且只列了前两格。）

### `GET /games/{appid}`

`appid` 在 `dwd_game` 里不存在时返回 `40401`。基本信息来自 `dwd_game`，类型来自 `dwd_game_genre`；`cluster`、`hot_pred`、`sentiment`、`peers` 四块分别来自模型结果表，对应的表里没有这款游戏时该块为 `null`。

| 字段 | 类型 | 说明 |
|---|---|---|
| `appid` | int | |
| `name` | string | |
| `header_image` | string \| null | 头图地址 |
| `release_date` | string \| null | 发行日期 |
| `release_year` | int \| null | 发行年份；未发行为 `null` |
| `price_usd` | number | 价格（美元） |
| `price_bucket` | string | 价格区间 |
| `genres` | string[] | 类型，可为空数组 |
| `developer` / `publisher` | string \| null | 第一个开发商 / 发行商 |
| `owners_low` / `owners_high` / `owners_mid` | int \| null | 拥有者区间的下界、上界、中值（份） |
| `peak_ccu` | int \| null | 历史峰值在线（人） |
| `review_cnt` | int | 评论数（条）= `positive + negative` |
| `positive_cnt` | int | 好评数（条） |
| `positive_rate` | number \| null | 好评率 |
| `avg_playtime_min` / `median_playtime_min` | int \| null | 平均 / 中位游玩时长（分钟） |
| `metacritic_score` | int \| null | Metacritic 分数，0–100 |
| `required_age` | int \| null | 年龄限制（岁） |
| `dlc_count` / `achievements` / `num_languages` | int \| null | DLC 数、成就数、支持语言数 |
| `platforms` | string[] | 支持的平台，取值 `windows` / `mac` / `linux` |
| `cluster.cluster_id` / `cluster.cluster_label` | int / string | 所属簇（`ads_game_cluster`） |
| `hot_pred.hot_prob` | number | 热销概率（`ads_hot_pred`） |
| `hot_pred.hot_pred` / `hot_pred.hot_actual` | bool | 预测标签 / 实际标签 |
| `hot_pred.is_test` | bool | 这款游戏是否在测试集里；为 `false` 时前端注明"模型训练时见过这款游戏" |
| `hot_pred.model_name` | string | 产生预测的模型 |
| `sentiment.sample_cnt` / `sentiment.positive_cnt` | int | 打分的评论条数 / 判为正向的条数（`ads_review_sentiment`） |
| `sentiment.positive_ratio` | number | 情感正向占比 = `positive_cnt ÷ sample_cnt` |
| `sentiment.method` | string | `model` 或 `voted_up` |
| `peers.cluster_id` / `peers.cluster_label` | int / string | 同类对比的参照范围：与这款游戏同簇的全部游戏 |
| `peers.game_cnt` | int | 同簇游戏数（款） |
| `peers.avg_price_usd` | number | 同簇平均价格（美元） |
| `peers.avg_positive_rate` | number | 同簇平均好评率（各游戏好评率的平均） |
| `peers.avg_owners_mid` | int | 同簇平均拥有者（份） |
| `peers.avg_playtime_min` | int | 同簇平均游玩时长（分钟） |

`peers` 由后端对 `ads_game_cluster` 里同一个 `cluster_id` 的行求平均得到；这款游戏不在 `ads_game_cluster` 里时，`cluster` 和 `peers` 都是 `null`。

```json
{
  "appid": 730,
  "name": "Counter-Strike 2",
  "header_image": "https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/730/header.jpg?t=1749053861",
  "release_date": "2012-08-21",
  "release_year": 2012,
  "price_usd": 0.0,
  "price_bucket": "free",
  "genres": ["Action", "Free To Play"],
  "developer": "Valve",
  "publisher": "Valve",
  "owners_low": 100000000,
  "owners_high": 200000000,
  "owners_mid": 150000000,
  "peak_ccu": 1013936,
  "review_cnt": 8815087,
  "positive_cnt": 7642084,
  "positive_rate": 0.8669,
  "avg_playtime_min": 33906,
  "median_playtime_min": 6237,
  "metacritic_score": null,
  "required_age": 0,
  "dlc_count": 1,
  "achievements": 1,
  "num_languages": 29,
  "platforms": ["windows", "linux"],
  "cluster": { "cluster_id": 2, "cluster_label": "爆款大作" },
  "hot_pred": { "hot_prob": 0.9312, "hot_pred": true, "hot_actual": true, "is_test": false, "model_name": "hot_rf" },
  "sentiment": { "sample_cnt": 20, "positive_cnt": 17, "positive_ratio": 0.85, "method": "model" },
  "peers": { "cluster_id": 2, "cluster_label": "爆款大作", "game_cnt": 812, "avg_price_usd": 14.37, "avg_positive_rate": 0.8421, "avg_owners_mid": 6200000, "avg_playtime_min": 2140 }
}
```

（基本信息是真实数据；`cluster`、`hot_pred`、`sentiment`、`peers` 为示意值，模型尚未运行，届时这四块实际返回 `null`。）

### `GET /games/{appid}/reviews-trend`

来自 `ads_game_review_trend`。`appid` 不存在返回 `40401`；游戏存在但没有评论返回 `[]`。数组按月份从早到晚，没有评论的月份不返回，前端按时间轴画线。

| 字段 | 类型 | 说明 |
|---|---|---|
| `month` | string | 月份，`"YYYY-MM"`（UTC） |
| `review_cnt` | int | 该月评论数（条） |
| `positive_cnt` | int | 该月好评数（条） |
| `positive_rate` | number | 该月好评占比 |

```json
[
  { "month": "2025-09", "review_cnt": 41230, "positive_cnt": 35870, "positive_rate": 0.87 },
  { "month": "2025-10", "review_cnt": 39875, "positive_cnt": 34291, "positive_rate": 0.86 }
]
```

（示意值。）

### `GET /games/{appid}/price-history`

来自 `dwd_price_history`。`appid` 不存在返回 `40401`；还没有价格快照返回 `[]`。数组按日期从早到晚。

| 字段 | 类型 | 说明 |
|---|---|---|
| `date` | string | 采集日期，`"YYYY-MM-DD"` |
| `price_usd` | number | 当日价格（美元） |

```json
[
  { "date": "2026-11-20", "price_usd": 29.99 },
  { "date": "2026-11-21", "price_usd": 19.49 }
]
```

（示意值，价格快照尚未开始采集。）
