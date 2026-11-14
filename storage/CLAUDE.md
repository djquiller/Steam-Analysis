# storage/ — 数据库（数据侧）

表结构以 `docs/schema.md` 为准；建库建表脚本是 `scripts/init_db.sql`。

## 本机主库

- 全部开发、全量数据和答辩演示都在 DJQuiller 的电脑上：本机 MySQL 8.4.11（Windows 服务 `MySQL84`，开机自启），地址 `127.0.0.1:3306`，不对局域网开放。
- `ods`、`dwd`、`ads` 三层都保留在本机。本机另装有 PostgreSQL 16，本项目不用。
- 答辩直接用本机跑全栈 + 本机全量库，不依赖网络，不需要导出快照。

## 账号分权

| 账号 | 使用方 | 权限 |
|---|---|---|
| `etl_writer` | 采集、清洗、建模脚本 | 三层读写 |
| `api_reader` | 后端 | 只对 `dwd`/`ads` 有 `SELECT` |
| root | 只在本机登录 | — |

## 样本库

`storage/sample/seed_sample.sql` 里每张 `dwd`/`ads` 表放几百到一千行真实子集，文件控制在几 MB 以内。Mili Review 时导入样本库即可在自己电脑上跑起全栈；`.env` 里的 `DB_HOST` 用来切换样本库和全量库。

## 改表流程

在 PR 里同时修改 `docs/schema.md` 并附上 `storage/migrations/V{n}__描述.sql`。Mili Review 通过、合并之后，才在主库执行迁移，并同步更新样本数据。

## 字符集

库、表、连接一律使用 `utf8mb4` / `utf8mb4_0900_ai_ci`，不用只支持 3 字节的 `utf8`（`utf8mb3`），否则评论里的 emoji 和部分 CJK 字符会写入失败或变成乱码。SQLAlchemy / PyMySQL 连接串带 `?charset=utf8mb4`；`mysqldump` 导出、导入时加 `--default-character-set=utf8mb4`。
