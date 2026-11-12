# 数据来源登记

> 维护方：数据组。每接入一个数据源追加一行；答辩"数据来源与规模"页与《数据质量报告》引用本表。

| 来源 | 链接 | 许可 / 使用条款 | 获取方式 | 获取日期 | 原始行数 | 落库表 |
|---|---|---|---|---|---|---|
| Steam Games Dataset（FronkonGames），`games.csv` | https://www.kaggle.com/datasets/fronkongames/steam-games-dataset | MIT（HF 镜像标注；下载时核对 Kaggle 页） | Kaggle CLI 下载（2026-11-08 版本，约 401 MB） | 2026-11-12 | 125,855 款（README 称 148,909，以实际文件为准） | `ods_game_kaggle` |
| Steam Reviews, Games and Tags（sergiodelcarpio），`reviews-*.parquet` | https://www.kaggle.com/datasets/sergiodelcarpio/steam-reviews （采集代码：https://github.com/sadelcarpio/steam-recsys-e2e） | other：评论原文归作者，游戏信息归 Valve 与发行商；数据由 Steam 公开 Web API 采集，限研究与教育用途 | Kaggle CLI 逐分片下载（2026-10-30 快照，共 13 个分片 reviews-000～012，每片 1000 万条，共约 23.5 GB） | 2026-11-12 起 | 121,312,346 条评论（说明文件） | `ods_review_kaggle` |
| Steam Store `appdetails` | https://store.steampowered.com/api/appdetails | Steam 订户协议 / API 使用条款 | API 增量 | | | `ods_app_detail` |
| SteamSpy | https://steamspy.com/api.php | SteamSpy 公开 API | API 增量 | | | `ods_steamspy` |
| Steam `appreviews` | https://store.steampowered.com/appreviews/{appid} | Steam API 使用条款 | API 增量 | | | `ods_review_api` |
| `GetNumberOfCurrentPlayers` | https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/ | Steam Web API 条款 | 定时任务（每小时） | | | `ods_ccu_snapshot` |

## 已知局限

- **评论集体量**：1.21 亿条，覆盖 18.5 万个 appid，截至 2026-10-30。元数据全量入库（不含原文，约 10–20 GB，以实测为准）；原文只为情感模型保留分层抽样（每款游戏最多 k 条，共约 110 万条）。
- **隐私**：评论集的 `user_id` 是不可逆哈希，本项目不入库、不展示；大屏不展示评论原文。数据集说明要求不得用于识别或联系评论者。
- **评论集的游戏表**没有拥有者估算、好评数、平均时长，所以游戏维度仍以 FronkonGames 游戏集为准，两者按 appid 关联。
- **游戏集的 `estimated_owners` 是区间字符串**（如 `"20000 - 50000"`），清洗时取中值写入 `owners_mid`；大部分游戏落在最低档 `0 - 20000`。
