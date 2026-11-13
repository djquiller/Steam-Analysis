# backend/ — FastAPI 服务（可视化组）

为大屏提供 REST API。返回信封、错误码、筛选参数、接口清单的唯一来源是 `docs/api.md`；所读表的字段与口径见 `docs/schema.md`。

## 目录约定

```
backend/app/
  main.py           创建 app、挂路由、全局异常处理（统一转成信封 + 错误码）
  core/config.py    pydantic-settings 读 .env（DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME）
  db.py             SQLAlchemy engine 与会话
  routers/          按 docs/api.md 分组：meta / overview / trend / rank / cluster / ecosystem / games
  services/         查询逻辑：筛选参数 → WHERE 条件 → 小表汇总
  schemas/          pydantic 响应模型（Swagger 据此生成文档）
backend/tests/      pytest
```

## 约定

- 只用 `api_reader` 账号连库，只读 `dwd_*` / `ads_*`。重计算缺失时找数据组补 `ads` 表，接口里只做过滤、`SUM … GROUP BY` 再汇总、排序、分页。
- 全局筛选参数解析集中在一处（如 `services/filters.py`），所有可筛选接口复用。这里统一处理两件事：
  - 没传 `genre` 时，聚合表加条件 `genre = '__ALL__'`；游戏粒度表在传了 `genre` 时才关联 `dwd_game_genre`（规则见 `docs/schema.md`"筛选维度约定"）；
  - `price_bucket` 按逗号拆开，校验取值后生成 `IN (...)` 条件。
- SQL 一律参数化；`genre` 等字符串参数校验在 `/meta/filters` 的取值内，非法返回 `40001`。
- 空结果返回 `code: 0` 与空数组；数据库异常捕获后返回 `50001` 并记录日志。
- 开启 CORS，允许前端开发地址。
- 新增或修改接口：先改 `docs/api.md`（PR），再写代码与 pydantic 模型，Swagger 与文档保持一致。

## 实际代码结构

在上面的目录约定之外还有三个文件：

| 文件 | 作用 |
|---|---|
| `app/tables.py` | 后端要读的 dwd / ads 表的 SQLAlchemy 定义（类型的权威来源仍是 `scripts/init_db.sql`）。查询都用 SQLAlchemy Core 写成通用 SQL，MySQL 和测试用的 SQLite 都能跑 |
| `app/errors.py` | 信封、错误码、全局异常处理：`ApiError` → 对应 code；请求参数校验失败 → `40001`；`SQLAlchemyError` → `50001` |
| `app/fmt.py` | 输出格式：时间转 ISO 8601 带 `Z`，金额保留 2 位，比率保留 4 位且分母为 0 返回 `null`，单款游戏评论数 < 10 不给好评率 |

`services/filters.py` 的 `get_filters` 是所有可筛选接口共用的依赖；`genre` 的合法取值缓存 5 分钟（`.env` 的 `GENRE_CACHE_SECONDS` 可改）。

## 测试

在 `backend/` 目录下运行：`python -m pytest`。

pytest 对每个接口覆盖三种情况：正常数据、空数据、非法参数。

- **大部分测试**用内存 SQLite：按 `app/tables.py` 建表，每个测试只插几行精确可控的数据，不依赖任何数据库，约 1 秒跑完。
- **`tests/test_live_db.py`**（标记 `live`）连 `.env` 配置的真实库，检查每个接口都返回 `code = 0`，并检查带全部筛选条件时单个接口不超过 2 秒；连不上库时自动跳过。只跑这部分：`python -m pytest -m live`。
- 样本库 `storage/sample/seed_sample.sql` 导出之后，把 `.env` 的 `DB_HOST`/`DB_NAME` 指向样本库，`live` 测试就是对样本库的冒烟测试。

## 本地运行

`.env`（仓库根目录那一份，后端直接读它）中 `DB_HOST` 指向本机样本库或主库（地址写在 `CLAUDE.local.md`）。在 `backend/` 目录下：

```
python -m uvicorn app.main:app --port 8000            # 启动
python -m uvicorn app.main:app --port 8000 --reload   # 开发时改代码自动重启
```

| 地址 | 内容 |
|---|---|
| `http://127.0.0.1:8000/api/v1/...` | 接口，清单见 `docs/api.md` |
| `http://127.0.0.1:8000/docs` | Swagger 交互文档 |
| `http://127.0.0.1:8000/health` | 存活检查，不查库 |

只读账号 `api_reader` 连库；允许跨域的前端地址默认是 Vite 的 `5173` 端口，可用 `.env` 的 `CORS_ORIGINS` 改。
