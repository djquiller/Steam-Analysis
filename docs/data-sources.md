# 数据来源登记

> 维护：DJQuiller；Review：Mili。每接入一个数据源追加一行；答辩"数据来源与规模"页与《数据质量报告》引用本表。

| 来源 | 链接 | 许可 / 使用条款 | 获取方式 | 获取日期 | 原始行数 | 落库表 |
|---|---|---|---|---|---|---|
| Steam Games Dataset（FronkonGames） | https://www.kaggle.com/datasets/fronkongames/steam-games-dataset （镜像：https://huggingface.co/datasets/FronkonGames/steam-games-dataset） | MIT（HF 镜像标注；下载时核对 Kaggle 页） | 文件下载 | 待下载 | README 称 148,909 款，HF 预览约 124k 行，以实际下载为准 | `ods_game_kaggle` |
| Steam Reviews Dataset 2021 | https://www.kaggle.com/datasets/najzeko/steam-reviews-2021 （镜像：https://huggingface.co/datasets/GianLucaSpagnolo/Steam_Reviews_Dataset_2021） | 待下载时核对 Kaggle 页 | 文件下载 | 待下载 | 约 21.7M 行，约 200 款游戏，28 种语言 | `ods_review_kaggle` |
| Steam Store `appdetails` | https://store.steampowered.com/api/appdetails | Steam 订户协议 / API 使用条款 | API 增量 | | | `ods_app_detail` |
| SteamSpy | https://steamspy.com/api.php | SteamSpy 公开 API | API 增量 | | | `ods_steamspy` |
| Steam `appreviews` | https://store.steampowered.com/appreviews/{appid} | Steam API 使用条款 | API 增量 | | | `ods_review_api` |
| `GetNumberOfCurrentPlayers` | https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/ | Steam Web API 条款 | 定时任务（每小时） | | | `ods_ccu_snapshot` |

## 已知局限

- **评论集只覆盖约 200 款热门游戏，且截止 2021 年初**。语言分布、活跃时段、时长分布反映的是热门游戏的玩家群体，图表口径与《数据质量报告》需注明。2021 年之后的评论由 `appreviews` 接口为 Top N 游戏增量补采。
- **游戏集的 `estimated_owners` 是区间字符串**（如 `"20000 - 50000"`），清洗时取中值写入 `owners_mid`；大部分游戏落在最低档 `0 - 20000`。
