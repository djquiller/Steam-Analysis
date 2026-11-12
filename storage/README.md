# storage/ — 数据库初始化（数据组）

表结构以 `docs/schema.md` 为准；建库建表脚本是 `scripts/init_db.sql`。

## 库划分

| 库 | 存放 | 谁能访问 |
|---|---|---|
| `steam_ods` | `ods_*` 原始数据 | 只有 `etl_writer` |
| `steam` | `dwd_*` 明细 + `ads_*` 聚合与模型结果 | `etl_writer` 读写，`api_reader` 只读 |

## 首次初始化（需要 root，由本机管理员执行）

1. 建库建表：

   ```
   mysql -u root -p -e "source scripts/init_db.sql"
   ```

   在仓库根目录执行。不用 `mysql … < 文件` 的写法，因为 PowerShell 不支持 `<` 输入重定向。

2. 用 root 登录 `mysql -u root -p`，执行下面的语句。`<…>` 换成你自己设定的密码，**密码只填进本机 `.env`，不写进仓库**：

   ```sql
   -- ETL 读写账号：只允许本机连接
   CREATE USER IF NOT EXISTS 'etl_writer'@'localhost' IDENTIFIED BY '<etl 密码>';
   GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, ALTER, INDEX,
         CREATE VIEW, SHOW VIEW, CREATE TEMPORARY TABLES
     ON steam_ods.* TO 'etl_writer'@'localhost';
   GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, ALTER, INDEX,
         CREATE VIEW, SHOW VIEW, CREATE TEMPORARY TABLES
     ON steam.* TO 'etl_writer'@'localhost';

   -- 后端只读账号：允许局域网连接（可视化组的电脑）
   CREATE USER IF NOT EXISTS 'api_reader'@'%' IDENTIFIED BY '<api 密码>';
   GRANT SELECT ON steam.* TO 'api_reader'@'%';
   ```

3. 复制 `.env.example` 为 `.env`，填入 `ETL_DB_PASSWORD` 和 `DB_PASSWORD`。

## 导入数据（游戏集 + 1.21 亿条评论）

前提：已完成上面的初始化，`.env` 已填好，Kaggle 令牌放在 `%USERPROFILE%\.kaggle\kaggle.json`，
已执行 `python -m pip install -r requirements.txt`。

在仓库根目录打开一个终端，运行：

```
python scripts/load_data.py
```

它会依次导入游戏集，再逐个处理评论的 13 个分片。每个分片依次执行：下载约 1.9 GB → 导入 `ods` → 抽样原文 → 清洗到 `dwd` → 删除分片文件。实测每个分片 6–18 分钟（表越大越慢），全部跑完约 3 小时，占用磁盘约 33 GB（数据库所在的盘）。

| 想做的事 | 命令 |
|---|---|
| 看进度：哪些分片做完了、各用了多久 | `python scripts/load_data.py --status` |
| 中断后继续（关了窗口、断网、重启电脑） | 再运行一次 `python scripts/load_data.py`，已完成的步骤会自动跳过 |
| 只跑某几个分片 | `python scripts/load_data.py --reviews 5-8` |
| 处理完保留分片文件 | 加 `--keep-files` |

- 运行期间可以正常用电脑，但不要关掉这个终端窗口；关掉了也没关系，重新运行即可续上。
- 进度记在数据库表 `steam_ods.etl_progress` 里；每一步的详细数字（行数、耗时）追加在 `data/logs/runs.jsonl`。
- 中途某个分片失败时（比如下载断了），这条命令会报错退出；直接重新运行即可，该分片未完成的步骤会先清掉半成品再重做。
- 下载中途被打断留下的残缺文件（同名的 `.kaggle-partial` 标记文件），再次运行时会自动删除并重新下载。
- 下载卡住不动（文件长时间不增长，常见于经过代理时连接半断）：按 `Ctrl+C` 后重新运行即可。

## 推荐的服务器设置（root 执行一次，重启后保留）

| 设置 | 作用 |
|---|---|
| `SET PERSIST local_infile = 1;` | 允许 `LOAD DATA LOCAL INFILE` 批量导入，导入 1.2 亿行评论快得多 |
| `SET PERSIST innodb_buffer_pool_size = 8589934592;` | InnoDB 缓冲池调到 8 GB，默认的 128 MB 对亿级评论表太小 |
