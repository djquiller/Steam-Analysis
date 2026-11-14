# Steam 平台游戏玩家生态与热销趋势可视化系统

课程综合项目（2 人组）。必须打通六环节流水线：**采集 → 存储 → 挖掘 → 后端 → 前端 → 可视化**，缺一个环节扣 8–10 分。课程要求已整理进下方"里程碑"与"评分细则速查"两节。

本文件是项目的统一约定。各模块的实现细节写在对应子目录的 `CLAUDE.md` 里，在哪个模块工作就读哪份。

## 分工

| 成员 | 角色 | 负责内容 |
|---|---|---|
| **DJQuiller**（当前用户） | 开发 | 六个环节全部的编码、建库、数据导入与文档 |
| **Mili** | Review | 审查所有 PR，批准后才能合并；不负责编码 |

六个环节仍按两个模块组划分目录，各子目录 `CLAUDE.md` 里的"数据组 / 可视化组"指的是模块组，不再对应不同的人：

| 模块组 | 环节 | 目录 | 契约 |
|---|---|---|---|
| **数据组** | 采集、存储、挖掘 | `crawler/` `storage/` `analysis/` | `docs/schema.md` |
| **可视化组** | 后端 API、前端大屏 | `backend/` `frontend/` | `docs/api.md` |

- **模块组之间的边界**：数据侧把 `dwd_*` 明细表、`ads_*` 聚合表和模型结果表写进 MySQL；后端只读这两层。即使同一个人写两边，这条边界也照样保留，答辩时作为分层设计来讲。
- 分工表与 M2 / M4 文档要如实写明：编码由 DJQuiller 完成，Mili 负责 Review。
- 答辩时两人都要能讲清全链路；Mili 通过 Review 熟悉各模块的关键设计。

## 契约文件

两个模块组之间的约定只记录在下面两份文件里，各处的 CLAUDE.md 只引用它们，不另抄一份：

- **`docs/schema.md`**：所有表的表名、字段、类型、口径，以及每张 `ads_*` 表对应哪个接口。
- **`docs/api.md`**：返回格式、错误码、全局筛选参数、接口清单。

改动任一契约文件都要发 PR 并 @ Mili Review。批准、合并之后，才能按新契约改代码或执行迁移。

## 技术栈

| 层 | 选型 |
|---|---|
| 采集 | Python 3.11 + requests/httpx + APScheduler |
| 存储 | MySQL 8，数仓分层 `ods → dwd → ads` |
| 挖掘 | pandas + numpy + scikit-learn |
| 后端 | FastAPI + SQLAlchemy + pydantic-settings + pytest |
| 前端 | Vue 3 + Vite + TypeScript + ECharts 5 + Pinia + axios |
| 环境 | Python 3.11、Node 20 LTS；Docker 选做 |

## 仓库结构

```
crawler/     采集（数据组）
storage/     建表 SQL、migrations/、sample/（数据组）
analysis/    清洗、聚合、建模、数据质量报告（数据组）
backend/     FastAPI 服务（可视化组）
frontend/    Vue 大屏（可视化组）
docs/        schema.md、api.md、data-sources.md、部署说明、M2 方案文档
scripts/     一键初始化：init_db.sql、load_data.py
```

## 数据分层与规模

- **`ods_*`**：原始数据，原样落库。
- **`dwd_*`**：清洗后的明细。
- **`ads_*`**：面向大屏的聚合结果表和模型结果表，基本一个看板模块对应一张表。

需要大量计算的聚合都由数据组预先算好写入 `ads`。后端只对 `ads` 小表做按条件过滤、`SUM … GROUP BY` 再汇总、排序和分页。为此，响应筛选的 `ads` 表要保留"年份 / 类型 / 价格区间"三个维度列，具体见 `docs/schema.md`。

**规模验收线**：
- 游戏 ≥ 8 万条，评论 ≥ 100 万条，在线人数快照持续积累。
- 附一份《数据质量报告》。
- 答辩时两人都要能说清"海量"体现在哪里。

## 数据库与本机环境

全部开发、全量数据和答辩演示都在 DJQuiller 的电脑上完成：

1. **主库**：本机 MySQL 8.4.11（Windows 服务 `MySQL84`，开机自启），地址 `127.0.0.1:3306`，不对局域网开放。`ods`、`dwd`、`ads` 三层都保留在本机。本机另装有 PostgreSQL 16，本项目不用。
2. **账号分权**：
   - `etl_writer`：采集与清洗、建模脚本使用，对三层都有读写权限。
   - `api_reader`：后端使用，只对 `dwd`/`ads` 有 `SELECT` 权限。
   - root 只在本机登录。
3. **开发样本库**：`storage/sample/seed_sample.sql` 里每张 `dwd`/`ads` 表放几百到一千行真实子集，文件控制在几 MB 以内。Mili Review 时导入样本库即可在自己电脑上跑起来；用 `.env` 里的 `DB_HOST` 切换样本库和全量库。
4. **改表流程**：在 PR 里同时修改 `docs/schema.md` 并附上 `storage/migrations/V{n}__描述.sql`。Mili Review 通过、合并之后，才在主库执行迁移，并同步更新样本数据。
5. **答辩演示**：直接用本机跑全栈 + 本机全量库，不依赖网络，也不需要导出快照。
6. **Python**：直接使用本机 Anaconda 的 Python 3.14.6（`C:\Users\Y7000P\anaconda3\python.exe`），不另建 3.11 环境。已自带 pandas 3.0.3、numpy 2.4.6、scikit-learn 1.9.0、pyarrow、SQLAlchemy 2.0、httpx、pydantic-settings、pytest、uvicorn；缺的包（pymysql、apscheduler、fastapi、kaggle 等）用到时按 `requirements.txt` 安装。
7. **Kaggle**：令牌放在 `%USERPROFILE%\.kaggle\kaggle.json`，由 DJQuiller 本人放置；Claude 不读取其内容。

## 工程规范

- **Git**：`main` 分支受保护；在 `feat/<模块>-<描述>` 分支上开发，通过 PR 合并，每个 PR 都由 Mili Review 批准后才能合并。有效提交 ≥ 12 次，"团队协作"这一项占 15%。
- **提交信息**：用 Conventional Commits 格式，作用域写模块名，例如 `feat(crawler): 新增评论分页采集`、`fix(frontend): ...`。
- **密钥**：Steam API Key 和数据库密码只写在 `.env`；仓库提交 `.env.example`，`.gitignore` 里要包含 `.env`。
- **依赖声明**：Python 用 `requirements.txt`，前端用 `frontend/package.json`。
- **可重跑初始化**：`scripts/init_db.sql` 加 `scripts/load_data.py`，克隆仓库、导入样本数据后就能跑起来。
- **注释**：关键模块写清楚"做什么、为什么"。
- **字符集**：全链路统一 UTF-8，换行统一 LF，由 `.editorconfig` 和 `.gitattributes` 约束；克隆仓库后执行 `git config core.quotepath false`，让中文文件名正常显示。
  - 文件：UTF-8 无 BOM。Windows 上的 PowerShell 5 和记事本默认可能写出 GBK 或带 BOM 的文件，统一改用 VS Code 保存；PowerShell 7 默认 UTF-8 无 BOM。
  - MySQL：库、表、连接一律使用 `utf8mb4` / `utf8mb4_0900_ai_ci`，不用只支持 3 字节的 `utf8`（`utf8mb3`），否则评论里的 emoji 和部分 CJK 字符会写入失败或变成乱码。SQLAlchemy / PyMySQL 连接串带 `?charset=utf8mb4`，`mysqldump` 导出、导入时也加 `--default-character-set=utf8mb4`。
  - Python：`open()`、`pandas.read_csv()`、`to_csv()` 一律显式传 `encoding="utf-8"`，不依赖系统默认编码（中文 Windows 默认是 GBK）；需要给 Excel 打开的 CSV 才用 `utf-8-sig`。在 Windows 终端运行脚本时设置 `PYTHONUTF8=1`。
  - 后端：FastAPI 默认以 UTF-8 输出 JSON；前端 `index.html` 写 `<meta charset="UTF-8">`。

## 里程碑（当前：准备 M2）

| 节点 | 学时 | 交付物 | 检查要点 | 占比 |
|---|---|---|---|---|
| M1 选题 | 15–16 | 《在线选题表》1 页 | 数据可获取、规模可达标、是真问题 | 10% |
| **M2 方案设计** | 17–18 | 《技术方案与架构设计文档》：架构图、选型对比与理由、数据模型、API 清单、计划、分工表 | 覆盖六环节、选型有论证、计划合理 | 20% |
| M3 中期检查 | 25–26 | 可运行原型（至少打通采集 → 存储，或有初步可视化）、进度报告、问题清单 | 至少 1 条链路跑通、进度过半 | 20% |
| M4 最终答辩 | 35–36 | 源码、部署包与部署文档、演示 PPT、现场演示 | 端到端可运行，回应了中期整改意见 | 50% |

**M4 交付物要点**：
- **源码**：按模块分目录，附可重跑的初始化脚本。
- **部署文档**：写明环境要求、依赖版本、启动步骤、端口与访问方式、默认账号、常见问题排查；另附局域网演示地址，或一段不少于 3 分钟的录屏。
- **演示 PPT**：12–18 页，依次包括背景与问题定义、数据来源与规模、架构图、选型理由、**现场演示**（不接受纯截图）、可视化成果与业务洞察、难点与解决方案、不足与改进、分工与个人贡献。
- **报告书**：选做，3000–5000 字。

## 评分细则速查

| 维度 | 权重 | 拿高分的要点 | 主要扣分项 |
|---|---|---|---|
| 功能完整性 | 30% | 六环节全部自研打通，现场演示流畅，有异常处理和降级，有亮点功能 | 缺环节；只能放录屏；依赖硬编码的假数据；接口报错没有提示 |
| 数据规模 | 15% | 达到百万级，来源可说明，有数据质量报告，用到数据库聚合 | 不到 10 万条且无合理说明；全程静态数据；没有质量校验 |
| 可视化效果 | 20% | 选型有论证，交互链路完整，视觉统一，大屏适配，能讲出一个故事 | 图表单一或选型错误；没有交互；缺单位和口径；地图不合规 |
| 工程规范性 | 20% | 分层清晰，按文档能跑起来，README、部署文档、接口文档齐全 | 代码堆在一个文件里；提交信息全是 update；密钥硬编码 |
| 团队协作 | 15% | 有分支、PR 和 Review 记录，每人都能讲清全链路，中期意见全部整改 | 一个人独占代码；分工表与实际贡献不符 |
