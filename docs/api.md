# 接口契约（API）

> **维护方：可视化组**。本文件是后端接口的唯一权威来源；运行时以 FastAPI 自带 Swagger（`/docs`）为准，本文件随之同步。修改需 PR 并由数据组 Review。
>
> 状态：**草案 v0.2**。老师尚未下发"标准数据契约"，下发后逐字段对齐并更新本文件。
>
> v0.2 变更：价格筛选由 `price_min`/`price_max` 改为按档位多选的 `price_bucket`；`/trend/price-rating` 改读 `ads_rating_dist`；注明游戏粒度接口如何按类型筛选。

## 返回信封

```json
{ "code": 0, "msg": "ok", "data": {} }
```

| code | 含义 |
|---|---|
| `0` | 成功（含空结果：`data` 为空数组/空对象，前端显示空态） |
| `40001` | 参数错误 |
| `40401` | 资源不存在（如 appid 不存在） |
| `50001` | 数据库异常 |

## 全局筛选参数

所有标注"可筛选"的接口都接受以下查询参数，全部可选：

| 参数 | 类型 | 说明 |
|---|---|---|
| `year_start` / `year_end` | int | 发行年份闭区间 |
| `genre` | string | 单个类型名，取值见 `/meta/filters`；不传表示全部类型（后端读 `__ALL__` 汇总行，见 `docs/schema.md`"筛选维度约定"） |
| `price_bucket` | string | 价格区间，可多选，逗号分隔，如 `free,lt10`；取值 `free` / `lt10` / `10_30` / `30_60` / `ge60`，与表中的档位一一对应；不传表示全部 |

价格区间直接按档位筛选，不接受任意金额：表里只存了档位，任意金额（如 ≤ 20 美元）无法精确换算。非法取值返回 `40001`。

## 接口清单

前缀 `/api/v1`。数据来源表见 `docs/schema.md`。

| 接口 | 可筛选 | 用途 | 来源表 |
|---|---|---|---|
| `GET /meta/filters` | | 筛选项（年份范围、类型列表、价格区间） | `dwd_game`, `dwd_game_genre` |
| `GET /meta/updated-at` | | 数据更新时间 | `ads_meta` |
| `GET /overview/kpi` | | 游戏总数 / 评论总数 / 估算玩家总量 / 实时在线峰值 | `ads_kpi_overview` |
| `GET /trend/yearly` | ✓ | 历年发行量与均价 | `ads_yearly_release` |
| `GET /trend/genres` | ✓ | 类型热度 | `ads_genre_heat` |
| `GET /trend/price-rating` | ✓ | 价格区间 × 好评率箱线（由 1% 分箱推算五数） | `ads_rating_dist` |
| `GET /rank/top-sellers?metric=owners\|ccu&limit=10` | ✓ | 热销 Top10 | `ads_top_sellers`（筛类型时关联 `dwd_game_genre`） |
| `GET /rank/online-live` | | 实时在线榜（前端 60 秒轮询） | `ads_ccu_latest` |
| `GET /cluster/games` | ✓ | 聚类散点 | `ads_game_cluster`（筛类型时关联 `dwd_game_genre`） |
| `GET /ecosystem/rating-dist` | ✓ | 好评率分布 | `ads_rating_dist` |
| `GET /ecosystem/review-languages` | ✓ | 评论语言分布 | `ads_review_lang` |
| `GET /ecosystem/playtime-dist` | ✓ | 游玩时长分布 | `ads_playtime_dist` |
| `GET /ecosystem/activity-heatmap` | ✓ | 星期 × 小时评论活跃度 | `ads_review_heatmap` |
| `GET /games/{appid}` | | 单款游戏详情（含预测、情感、聚类标签） | `dwd_game`, `ads_hot_pred`, `ads_review_sentiment`, `ads_game_cluster` |
| `GET /games/{appid}/reviews-trend` | | 评论量与好评率月度走势 | `ads_game_review_trend` |
| `GET /games/{appid}/price-history` | | 价格历史 | `dwd_price_history` |

各接口 `data` 的具体结构在实现时补到对应小节（TODO）。
