# crawler/ — 采集（数据组）

把数据从外部来源落到 MySQL `ods_*` 层。表结构以 `docs/schema.md` 为准；每个新数据源登记到 `docs/data-sources.md`（名称、链接、许可、下载/采集日期、行数）。

## 数据源

| 来源 | 用途 | 限流与注意 |
|---|---|---|
| Kaggle 公开数据集 | 游戏全量、历史评论打底 | 选评论集时核对字段：`timestamp_created`、`language`、`playtime_at_review`、`voted_up` 缺一不可，大屏热力图 / 语言分布 / 时长分布 / 情感标签都依赖它们 |
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

## 定时任务

`GetNumberOfCurrentPlayers` 与价格快照由 APScheduler 常驻进程执行，体现"定时增量采集"加分项。部署说明里写清启动方式；答辩前确认快照已连续积累数天。

## 待补（数据组填写）

- [ ] 选定的 Kaggle 数据集及其字段映射
- [ ] 各脚本入口与运行命令
- [ ] 实测限流与总采集耗时
