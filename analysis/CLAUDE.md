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

## 待补

- [ ] "热销"标签的最终定义
- [ ] 聚类最终 K 值与各簇业务含义
- [ ] 各脚本入口与运行命令
