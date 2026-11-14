# analysis/ — 清洗、聚合、建模（数据侧）

负责 `ods → dwd → ads` 的全部加工，用 `etl_writer` 账号写库。字段与口径的唯一来源是 `docs/schema.md`；新增或修改表先走契约 PR。

## 流水线

1. **清洗 `ods → dwd`**（pandas）：去重、类型转换、缺失处理、异常值处理，按 `docs/schema.md` 的全局口径统一货币、价格区间、年份、类型拆行。
2. **聚合 `dwd → ads`**：SQL 聚合为主（体现"数据库聚合"评分点），一个看板模块一张表。响应筛选的表保留 `release_year`、`genre`、`price_bucket` 三列，让后端能 `WHERE` 后再小表汇总。
3. **建模**：结果写入 `ads_*` 模型表。
4. **刷新元信息**：每次跑完更新 `ads_meta`（数据更新时间、各表行数）。

每一步都可单独重跑，整条流水线由 `scripts/load_data.py` 串起来。

## 数据质量报告

产出 `analysis/reports/data_quality.md`，至少包含：每张 dwd 表清洗前后行数、各字段缺失率、去重数、异常值规则与剔除数、最终规模是否达标（游戏 ≥ 8 万、评论 ≥ 100 万）。答辩"数据规模"占 15%，这份报告是依据。

## 模型

| 模型 | 方法 | 输出表 | 说明 |
|---|---|---|---|
| 游戏聚类 | KMeans；特征：价格、好评率、拥有者（取对数）、平均时长；先标准化，肘部法 + 轮廓系数定 K | `ads_game_cluster` | 每簇给业务标签（如"爆款大作 / 小众精品 / 免费引流"）；用 PCA 降到二维写 `x`/`y` 供散点图 |
| 热销预测 | RandomForest 与 LogisticRegression 对比；标签需先定义"热销"阈值（如拥有者前 10%） | `ads_hot_pred`、`ads_model_metrics` | 记录准确率、F1、AUC，满足"模型调优与对比"加分项 |
| 评论情感 | TF-IDF + LogisticRegression，`voted_up` 作标签 | `ads_review_sentiment` | 时间不够时降级为直接统计 `voted_up` |

模型脚本固定随机种子，保证结果可复现。

### 热销预测的标签与特征

- **标签**：`owners_mid` 不低于全体游戏第 90 百分位的游戏记为热销（1），其余为 0。`owners_mid` 是离散档位，同档并列的全部计入热销，实际正样本比例写进模型报告。
- **特征只用发行前就能知道的信息**：价格、类型（多热编码）、发行年份、支持平台数、支持语言数、DLC 数、成就数、年龄限制、开发商历史作品数。`positive`、`negative`、`peak_ccu`、平均时长这类发行后才有的指标与拥有者高度相关，放进去等于泄露标签，一律不用。
- **评估**：分层抽样 8:2 划分，类别不平衡用 `class_weight="balanced"`，主要看 F1 和 AUC，准确率只作参考。

### 聚类 K 值

在 K = 3–8 范围内，用肘部法和轮廓系数选 K，最终 K 值与各簇业务含义在拿到全量数据后确定。

## 脚本与运行命令

在仓库根目录执行。

| 脚本 | 作用 | 命令 |
|---|---|---|
| `analysis/build_dwd_game.py` | `ods_game_kaggle` → `dwd_game` + `dwd_game_genre`（全量重建） | `python -m analysis.build_dwd_game` |
| `analysis/build_dwd_review.py` | `ods_review_kaggle` → `dwd_review`（按分片，`INSERT … SELECT`） | `python -m analysis.build_dwd_review --shards 0-12` |
| `analysis/build_ads_game.py` | `dwd_game` + `dwd_game_genre` → 只依赖游戏表的 `ads` 表：`ads_yearly_release`、`ads_genre_heat`、`ads_rating_dist`、`ads_top_sellers`（拥有者口径），并更新 `ads_kpi_overview` 的游戏侧两列和 `ads_meta`。全量重建，单事务，提交前自动核对总数。依赖评论表、在线快照、模型的 `ads` 表不在此脚本内 | `python -m analysis.build_ads_game` |
| `analysis/build_ads_review.py` | `dwd_review` → 依赖评论表的 `ads` 表：`ads_review_lang`、`ads_playtime_dist`、`ads_review_heatmap`、`ads_game_review_trend`，并更新 `ads_kpi_overview.review_cnt` 和 `ads_meta`。分两步：先按 appid 区间分块，把 1.21 亿行评论压成四张"游戏 × 维度"的中间表 `steam_ods.stg_review_*`（READ COMMITTED、每块单独提交）；再在一个事务里由中间表关联游戏与类型写入 `ads`，提交前核对中间表合计与直接扫 `dwd_review` 的结果、`ads` 与中间表的合计。`--reuse-stage` 跳过第一步 | `python -m analysis.build_ads_review` |
| `analysis/build_quality_report.py` | 直接查库生成《数据质量报告》`analysis/reports/data_quality.md`：规模验收、各层行数与剔除原因、缺失率、唯一性、异常值、一致性核对。评论侧统计取自上面的中间表，只有清洗规则命中数要扫一遍 `ods_review_kaggle`。需先跑 `build_ads_review` | `python -m analysis.build_quality_report` |

**实测（2026-11-12 全量）**

| 项 | 数值 |
|---|---|
| 游戏清洗 | 12.6 秒，得到 125,854 款游戏、338,583 条游戏 × 类型、33 种类型 |
| 评论清洗 | `dwd_review` 共 121,312,346 行，与 `ods` 行数一致，无丢弃；累计 56.9 分钟（第 0 片 143 秒，第 10 片 415 秒） |
| 评论涉及的游戏 | 124,757 个 appid；其中 108,562 个在 `dwd_game` 里，16,195 个不在（聚合时关联 `dwd_game`，这部分不进 `ads`） |
| 游戏覆盖 | `dwd_game` 125,854 款中 108,562 款有评论（86.3%）；Steam 计数评论 ≥ 10 条的 56,662 款中 54,716 款有评论（96.6%） |
| 与 Steam 计数对比 | 入库 121,312,346 条，是游戏集里好评 + 差评合计 148,894,107 的 81.5% |
| 占用（`steam`） | 约 13 GB，几乎全部是 `dwd_review` |

**实测（2026-11-14，评论侧 ads 与质量报告）**

| 项 | 数值 |
|---|---|
| `build_ads_review` 第一步 | 24 块，495 秒；中间表 `stg_review_lang` 94.5 万行、`stg_review_playtime` 60.8 万行、`stg_review_hour` 594 万行、`stg_review_month` 271 万行，四张表合计都是 121,312,346 |
| `build_ads_review` 第二步 | 229 秒：直接扫 `dwd_review` 取核对基准 65 秒，`ads_review_heatmap` 129 秒（中间表最大、关联类型后约 2200 万行再分组），其余三张表合计约 26 秒 |
| 评论侧 `ads` 行数 | `ads_review_lang` 28,071；`ads_playtime_dist` 11,182；`ads_review_heatmap` 165,977；`ads_game_review_trend` 2,658,672 |
| 进入 `ads` 的评论 | 117,777,463 条（所评游戏不在游戏集里的 3,534,859 条、所评游戏未发行的 24 条不进）；16 项核对全部一致 |
| `build_quality_report` | 约 100 秒，其中扫 `ods_review_kaggle` 一遍约占一半 |

## 待补

- [x] "热销"标签的最终定义（见上节）
- [ ] 聚类最终 K 值与各簇业务含义（方法已定，数值待全量数据）
- [x] 各脚本入口与运行命令（见上节）
- [x] 游戏与评论全量清洗到 `dwd`（2026-11-12 完成，数字见上节）
- [x] 生成 `ads` 聚合表（游戏侧、评论侧已写好，各在单独分支上等 Review）
- [x] 数据质量报告 `analysis/reports/data_quality.md`（脚本生成，数据变了就重跑）
