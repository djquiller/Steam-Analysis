# frontend/ — Vue 大屏（可视化组）

数据只从后端 API 取，接口与返回结构以 `docs/api.md` 为准；字段口径（单位、估算方式）见 `docs/schema.md`，图表上的单位与口径说明从那里取。

## 故事线与布局

大屏讲一条线：**市场在变 → 玩家在想什么 → 什么游戏会火**。不挤在一屏里，而是分成 4 个标签页，**每页最多 4 张大卡片**，避免观众在 3–5 米外看一屏十几张小图而眼睛疲劳。标签页是子路由，可以直接用链接打开某一页，也可以自动轮播。

顶栏常驻：标题、标签页导航、自动轮播开关、数据更新时间；第二行是全局筛选条（年份 / 类型 / 价格区间），切换标签页时筛选保持不变。

| 标签页 | 路由 | 卡片 | 图表 | 接口 |
|---|---|---|---|---|
| 01 总览 | `/overview` | 4 个 KPI 卡：游戏总数 / 评论总数 / 估算玩家总量 / 实时在线峰值 | 翻牌数字 | `/overview/kpi` |
| | | 历年发行量与均价（主视觉） | 柱线双轴 | `/trend/yearly` |
| | | 实时在线榜（60 秒轮询） | 滚动榜单 | `/rank/online-live` |
| 02 市场在变 | `/market` | 类型热度（点击联动全局筛选） | 矩形树图 | `/trend/genres` |
| | | 价格区间 × 好评率 | 箱线图 | `/trend/price-rating` |
| 03 玩家在想什么 | `/players` | 好评率分布、评论语言分布、游玩时长分布、评论活跃时段（2 × 2） | 直方图 / 条形图 / 直方图 / 热力图 | `/ecosystem/*` |
| 04 什么游戏会火 | `/hits` | 热销 Top10（可切换"拥有者 / 在线人数"口径） | 动态排序条形图 | `/rank/top-sellers` |
| | | 游戏聚类分群 | 散点图 | `/cluster/games` |
| 详情页 | `/game/:appid` | 基本信息、关键指标、聚类 / 热销预测 / 情感、评论趋势、价格历史、同类对比 | 组合 | `/games/{appid}…` |

切页：点标签、键盘 `←` `→` 或 `1`–`4`；「自动轮播」每页停留 30 秒（`src/views/tabs/registry.ts` 的 `CAROUSEL_SECONDS`），手动切页即停止。

### 屏幕适配

以 1920×1080 为基准按 `min(宽 / 1920, 高 / 1080)` 等比缩放，再把画布补齐到窗口比例，**铺满整个窗口、不留黑边**（`ScreenContainer.vue`）：

| 屏幕 | 缩放 | 画布（设计稿像素） |
|---|---|---|
| 1920×1080（16:9） | 1× | 1920×1080 |
| 2560×1440（QHD 16:9） | 1.33× | 1920×1080 |
| 2560×1600（16:10） | 1.33× | 1920×1200，多出的高度分给卡片 |
| 比 16:9 更宽的窗口 | 按高度 | 宽度大于 1920，多出的宽度分给卡片 |

所以写样式时按"至少 1920×1080"设计，布局一律用 grid / flex，不要写死总宽高。2026-11-13 在 2560×1440、2560×1600、2000×905、1440×1080 下实测：四个标签页与详情页都没有溢出或被裁切的卡片。

## 交互（三层都要做）

1. **全局筛选**：状态集中在 Pinia `stores/filters.ts`；筛选变化时所有可筛选图表重新请求。价格区间用 5 个档位的多选控件，不用连续滑块（与 `docs/api.md` 的 `price_bucket` 参数一致）。
2. **图表联动**：点击树图的某个类型 → 写入 `filters.genre` → 其他图表随之过滤；再次点击或点"重置"取消。
3. **下钻**：点击 Top10 条目或聚类散点 → 路由到 `/game/:appid`。

## 图表规范

"可视化效果"占 20%，每个图表组件按此执行：

- 标题旁写明**单位与口径**，如"拥有者（SteamSpy 区间估算中值）"、"时间（UTC）"。
- 类别 > 5 个用条形图或树图；饼图仅用于 ≤ 5 类的占比。
- **三态**：加载中 / 空数据 / 报错，统一由 `BaseChart` 处理；接口失败时提示并保留上次成功的数据作为降级。
- 地域构成用评论语言分布表达，大屏只使用自有数据图表（地图需审图号合规底图，本项目不引入）。
- 颜色、字号、数字格式全部来自 `theme/`，组件内只引用主题。

## 视觉 token（深青黑 + 毛玻璃 + Steam 蓝）

2026-11-13 参考 Dribbble 上的深色控制台设计改版：底色更深，卡片改为半透明毛玻璃（大圆角、微光描边、模糊背景），背景加几团柔和光晕；主强调色仍是 Steam 蓝。

| token | 值 | 用途 |
|---|---|---|
| `--bg-base` | `#0b1218` | 页面底色（深青黑） |
| `--bg-panel` | `rgba(20, 34, 46, 0.62)` | 毛玻璃卡片，配 `backdrop-filter: blur(14px)` |
| `--glass-border` | `rgba(102, 192, 244, 0.18)` | 卡片描边 |
| `--bg-raised` | `#2a475e` | 输入框边框、悬浮层 |
| `--accent` | `#66c0f4` | 主强调、第一系列 |
| `--text-primary` | `#d3dee7` | 正文 |
| `--positive` / `--negative` | `#a4d007` / `#c35c2c` | 好评 / 差评 |
| `--radius` / `--gap` | `16px` / `20px` | 卡片圆角 / 间距 |

字号阶梯（设计稿像素）：`--fs-small` 14、`--fs-body` 16、`--fs-title` 22（卡片标题）、`--fs-kpi` 64（KPI 数字）。图表里的字号从 `steam-dark.ts` 的 `font` 取，坐标轴与标签不小于 14。

ECharts 主题在 `src/theme/steam-dark.ts` 中 `registerTheme`，CSS 变量在 `src/theme/tokens.css`，两边改色要一起改。

## 字体

**只用随前端打包的本地无衬线字体**，不用系统字体，也不从 CDN 加载，保证任何电脑（包括断网的答辩现场）显示一致。在 `src/theme/fonts.ts` 引入：

| 字体 | 用途 | 包 |
|---|---|---|
| Inter（latin 子集，400 / 600 / 700） | 拉丁字母、数字；全局开 `tnum` 等宽数字，翻牌和榜单滚动不跳动 | `@fontsource/inter` |
| Noto Sans SC 思源黑体（400 / 700） | 中文 | `@fontsource/noto-sans-sc` |

字体栈统一为 `'Inter', 'Noto Sans SC', sans-serif`（CSS 变量 `--font-body`、ECharts 的 `FONT_FAMILY`）。Noto Sans SC 每个字重按 unicode-range 切成约 100 个小文件，浏览器只下载页面上出现的字所在的分片。两者都是 SIL OFL 1.1 许可。

ECharts 画在 canvas 上，字体分片晚到时不会自己重画，所以 `BaseChart` 监听 `document.fonts` 的 `loadingdone`，字体到齐后整体重绘一次。

## 目录约定

```
src/
  api/              axios 实例（解包 {code,msg,data}，code ≠ 0 抛错）+ 按 docs/api.md 分组的请求函数
  stores/filters.ts 全局筛选状态
  theme/            steam-dark.ts、tokens.css
  components/layout/ScreenContainer.vue   以 1920×1080 为基准等比缩放并铺满窗口
  components/charts/BaseChart.vue        init / resize / dispose / 三态
  components/charts/*.vue                每个看板模块一个组件
  views/Dashboard.vue、views/GameDetail.vue
  views/tabs/       四个标签页（OverviewTab / MarketTab / PlayersTab / HitsTab）与 registry.ts
```

实际还有：

| 位置 | 作用 |
|---|---|
| `src/charts/echarts.ts` | ECharts 按需注册（柱、线、树图、箱线、散点、热力图），并加载主题 |
| `src/composables/useRemote.ts` | 每个图表的请求都走它：依赖（筛选条件）变化自动重新请求并取消上一个；失败时保留旧数据；后端不可用时按 5 / 15 / 30 / 60 秒自动重试，恢复后各图自己好起来 |
| `src/theme/format.ts` | 数字与时间格式：亿 / 万、千分位、百分比、美元、UTC 转本地时间 |
| `src/components/layout/Panel.vue` | 毛玻璃卡片外壳：标题 + 单位与口径说明 + 右上角操作区 |
| `src/components/layout/Segmented.vue` | 卡片右上角的分段切换（口径、分箱宽度） |
| `src/components/dashboard/` | 顶栏（标题、标签页、轮播、全局筛选、更新时间）与 KPI 卡（数字滚动） |
| `src/theme/fonts.ts` | 本地字体引入与 `FONT_FAMILY` |

## 本地运行

需要 Node `^20.19` 或 `>=22.12`（Vite 7 的要求）。先按 `backend/CLAUDE.md` 启动后端（默认 `127.0.0.1:8000`），再在 `frontend/` 下：

```
npm install        # 第一次
npm run dev        # 开发服务器 http://127.0.0.1:5173，/api 自动代理到后端
npm run build      # 类型检查（vue-tsc）+ 打包到 dist/
npm run preview    # 预览打包结果
```

| 环境变量（可选，写在 `frontend/.env.local`） | 作用 |
|---|---|
| `VITE_BACKEND_URL` | 开发代理指向的后端地址，默认 `http://127.0.0.1:8000` |
| `VITE_API_BASE` | 接口前缀，默认 `/api/v1`；前后端不同源部署时改成完整地址 |

## 已验证的交互（2026-11-13，本机全量库）

- 点树图「RPG」：下拉框同步为 RPG，其余可筛选图表按 RPG 重新请求，树图高亮 RPG；再点或点「重置」取消。
- 点 Top10 条形 → `/game/:appid` 详情页；返回大屏时筛选状态保留（`KeepAlive`）。
- Top10 切到「在线人数」：还没有在线快照聚合时显示空态。
- 停掉后端：已有数据的图保留旧图并标「数据未更新」，没有数据的图显示错误与「重试」；后端恢复后自动重试成功，无需手动操作。
- 四个标签页点击切换、键盘切换都正常；自动轮播 30 秒后切到下一页，按方向键即停止。
- 切页动效用 CSS 动画（新页面插入即播放），不用 `<Transition mode="out-in">`：后者靠 `requestAnimationFrame` 推进离场，浏览器被遮挡或在后台时帧回调暂停，曾出现旧页卡在离场、新页不挂载的空白页。
- 字体请求全部指向本机开发服务器（`/node_modules/@fontsource/...woff2`），没有外部请求。
