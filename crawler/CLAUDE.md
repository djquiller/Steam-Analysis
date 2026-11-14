# crawler/ — 采集（数据侧）

把数据从外部来源落到 MySQL `ods_*` 层。表结构以 `docs/schema.md` 为准；每个新数据源登记到 `docs/data-sources.md`（名称、链接、许可、下载/采集日期、行数）。

## 数据源

| 来源 | 用途 | 限流与注意 |
|---|---|---|
| Kaggle 公开数据集 | 游戏全量、全量评论元数据 | 评论集必须有发表时间、语言、写评论时的游玩时长、是否推荐四个字段，大屏热力图 / 语言分布 / 时长分布 / 情感标签都依赖它们 |
| Steam Store `appdetails` | 游戏详情、价格、类型 | 约 200 次 / 5 分钟；价格统一请求 `cc=us` |
| SteamSpy | 拥有者区间、标签、平均时长 | 约 1 次 / 秒；`all` 接口约 1 次 / 分钟 |
| Steam `appreviews` | 增量评论 | `cursor` 翻页，`num_per_page` 最大 100；`cursor` 需 URL 编码，同一 cursor 重复出现即到底 |
| `ISteamUserStats/GetNumberOfCurrentPlayers` | 在线人数快照 | 需 Steam Web API Key；APScheduler 每小时采 Top 游戏一次，写 `ods_ccu_snapshot` |

（限流数字为经验值，首次采集时实测并更新本表。）

## 编写约定

- 公共 HTTP 客户端：统一超时、重试（指数退避）、限速与 User-Agent，所有采集脚本复用。
- **断点续采**：长任务把进度（已采 appid / 当前 cursor）持久化，重启从断点继续；写入用 `INSERT … ON DUPLICATE KEY UPDATE`，保证可重跑、不产生重复。
- 原始响应原样写 `ods`，清洗留给 `analysis/`。
- 每次运行打印并记录：来源、起止时间、请求数、失败数、入库行数——这些数字进入《数据质量报告》和答辩 PPT 的"数据来源与规模"页。
- Steam API Key 与数据库连接（`etl_writer` 账号）只从 `.env` 读取。
- Kaggle 令牌放在 `%USERPROFILE%\.kaggle\kaggle.json`，由 DJQuiller 本人放置；Claude 不读取其内容。

## 定时任务

`GetNumberOfCurrentPlayers` 与价格快照由 APScheduler 常驻进程执行，体现"定时增量采集"加分项。部署说明里写清启动方式；答辩前确认快照已连续积累数天。

## Kaggle 数据集与字段映射

数据集登记见 `docs/data-sources.md`。原始 CSV 原样导入 `ods`，下表是 `analysis/` 清洗到 `dwd` 时的映射：

| 源字段 | → `dwd` 字段 | 处理 |
|---|---|---|
| 游戏集 `appID` | `dwd_game.appid` | 转整数 |
| `release_date`（如 `"Aug 1, 2023"`） | `release_date`、`release_year` | 按 `%b %d, %Y` 解析，失败的不进 `ads` |
| `price` | `price_usd`、`price_bucket` | 已是美元 |
| `estimated_owners`（如 `"20000 - 50000"`） | `owners_mid` | 取区间中值 |
| `positive` / `negative` | 同名 | — |
| `average_playtime_forever` | `avg_playtime_min` | 单位：分钟 |
| `genres`（列表） | `dwd_game_genre` | 拆行 |
| `developers` / `publishers`（列表） | `developer` / `publisher` | 取第一个 |
| 评论集 `review_id` / `game_id` / `language` | 同名 / `appid` / 同名 | — |
| `reviewed_at`（UTC） | `timestamp_created` | 去掉时区，按 UTC 存 `DATETIME` |
| `is_positive` | `voted_up` | 与 `appreviews` 接口的 `voted_up` 同义 |
| `playtime_at_review` | `playtime_at_review_min` | 单位：分钟 |

评论集是 Parquet 分片（每片约 1.9 GB）。导入时逐片下载，只读取需要的列，不读评论原文和 `user_id`，导入后删除分片文件。评论原文只为情感模型另外抽样保留。评论集已覆盖到 2026 年，所以 `appreviews` 增量补采降为可选项。

## 在线人数采集的游戏范围

游戏集中 `peak_ccu` 最高的 500 款，加上 `owners_mid` 最高的 500 款，去重后作为每小时采集的名单，大约 600–800 款。名单每天随价格快照刷新一次。

## 脚本与运行命令

在仓库根目录执行；需要先完成 `storage/README.md` 的初始化并填好 `.env`。每次运行都会追加一行到 `data/logs/runs.jsonl`。

| 脚本 | 作用 | 命令 |
|---|---|---|
| `crawler/kaggle_games.py` | 下载 `games.csv` 并导入 `ods_game_kaggle` | `python -m crawler.kaggle_games` |
| `crawler/kaggle_reviews.py` | 逐片下载评论分片并导入 `ods_review_kaggle` | `python -m crawler.kaggle_reviews --shards 0-12 --delete-after` |
| `crawler/kaggle_review_text.py` | 评论原文按游戏分层抽样（每款最多 30 条），写入 `ods_review_text_sample` | `python -m crawler.kaggle_review_text --shard 0 --k 30` |
| `scripts/load_data.py` | 一键流水线：游戏集 + 13 个评论分片，逐片下载 → `ods` → 抽样 → `dwd`，可断点续跑 | `python scripts/load_data.py` |

公共模块在 `crawler/common/`：`settings.py`（读 `.env`）、`db.py`（`etl_writer` 连接）、`runlog.py`（运行记录）。

**实测（2026-11-12 全量，本机 i7-14650HX / 32 GB / NVMe）**

| 项 | 数值 |
|---|---|
| 游戏集 | 125,855 行，导入 22 秒 |
| 评论元数据 | 13 个分片共 121,312,346 行，全部进入 `ods_review_kaggle`，与数据集说明的总数一致 |
| 评论导入耗时 | 累计 57.5 分钟；第 0 片 138 秒，表变大后逐片变慢，第 11 片 522 秒 |
| 原文抽样 | 保留 2,335,697 条，覆盖 124,757 款游戏、31 种语言，每款最多 30 条；累计 18.7 分钟 |
| 下载 | 5–27 MB/s，一个分片 1–6 分钟；经过代理时出现过一次连接半断（见 `storage/README.md`） |
| 占用（`steam_ods`） | 约 20 GB：评论元数据约 16 GB，原文样本约 3 GB，游戏约 0.7 GB |

## 待补

- [x] 选定的 Kaggle 数据集及其字段映射（见上节；下载后核对列名和许可）
- [x] 各脚本入口与运行命令（见上节）
- [x] Kaggle 游戏集与评论集全量导入 `ods`（2026-11-12 完成，数字见上节）
- [x] 申请 Steam Web API Key 并填入 `.env`（2026-11-12 已校验可用）
- [ ] 在线人数与价格的定时采集（APScheduler）
- [ ] 实测 Steam / SteamSpy 接口限流与总采集耗时
