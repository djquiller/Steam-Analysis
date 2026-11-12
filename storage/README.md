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

## 推荐的服务器设置（root 执行一次，重启后保留）

| 设置 | 作用 |
|---|---|
| `SET PERSIST local_infile = 1;` | 允许 `LOAD DATA LOCAL INFILE` 批量导入，导入 1.2 亿行评论快得多 |
| `SET PERSIST innodb_buffer_pool_size = 8589934592;` | InnoDB 缓冲池调到 8 GB，默认的 128 MB 对亿级评论表太小 |
