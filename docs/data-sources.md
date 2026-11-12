# 数据来源登记

> 维护方：数据组。每接入一个数据源追加一行；答辩"数据来源与规模"页与《数据质量报告》引用本表。

| 来源 | 链接 | 许可 / 使用条款 | 获取方式 | 获取日期 | 原始行数 | 落库表 |
|---|---|---|---|---|---|---|
| TODO：Kaggle 游戏数据集 | | | 文件下载 | | | `ods_game_kaggle` |
| TODO：Kaggle 评论数据集 | | | 文件下载 | | | `ods_review_kaggle` |
| Steam Store `appdetails` | https://store.steampowered.com/api/appdetails | Steam 订户协议 / API 使用条款 | API 增量 | | | `ods_app_detail` |
| SteamSpy | https://steamspy.com/api.php | SteamSpy 公开 API | API 增量 | | | `ods_steamspy` |
| Steam `appreviews` | https://store.steampowered.com/appreviews/{appid} | Steam API 使用条款 | API 增量 | | | `ods_review_api` |
| `GetNumberOfCurrentPlayers` | https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/ | Steam Web API 条款 | 定时任务（每小时） | | | `ods_ccu_snapshot` |
