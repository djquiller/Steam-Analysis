# backend/ — FastAPI 服务（可视化侧）

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

- 只用 `api_reader` 账号连库，只读 `dwd_*` / `ads_*`。缺少的重计算先在 `analysis/` 里补成 `ads` 表，接口里只做过滤、`SUM … GROUP BY` 再汇总、排序、分页。
- 全局筛选参数解析集中在一处（如 `services/filters.py`），价格区间在这里换算为 `price_bucket` 集合，所有可筛选接口复用。
- SQL 一律参数化；`genre` 等字符串参数校验在 `/meta/filters` 的取值内，非法返回 `40001`。
- 空结果返回 `code: 0` 与空数组；数据库异常捕获后返回 `50001` 并记录日志。
- 开启 CORS，允许前端开发地址。
- 新增或修改接口：先改 `docs/api.md`（PR），再写代码与 pydantic 模型，Swagger 与文档保持一致。

## 测试

pytest 对每个接口覆盖三种情况：正常数据、空数据、非法参数。测试库使用 `storage/sample/seed_sample.sql` 导入的样本库。

## 本地运行

`.env` 中 `DB_HOST` 指向本机样本库或本机全量主库（见根目录 `CLAUDE.md`"数据库与本机环境"）。启动命令与端口在实现后补充到此处和部署文档。
