# frontend/ — Vue 大屏（可视化侧）

数据只从后端 API 取，接口与返回结构以 `docs/api.md` 为准；字段口径（单位、估算方式）见 `docs/schema.md`，图表上的单位与口径说明从那里取。

## 故事线与布局

主屏讲一条线：**市场在变 → 玩家在想什么 → 什么游戏会火**。设计稿 1920×1080，等比缩放。

| 区域 | 模块 | 图表 | 接口 |
|---|---|---|---|
| 顶部 | 标题、全局筛选栏、数据更新时间 | — | `/meta/filters`, `/meta/updated-at` |
| 顶部 | 4 个 KPI 卡：游戏总数 / 评论总数 / 估算玩家总量 / 实时在线峰值 | 翻牌数字 | `/overview/kpi` |
| 左栏·热销趋势 | 历年发行量与均价 | 柱线双轴 | `/trend/yearly` |
| | 类型热度 | 矩形树图 | `/trend/genres` |
| | 价格区间 × 好评率 | 箱线图 | `/trend/price-rating` |
| 中栏·核心 | 热销 Top10（可切换"拥有者 / 在线人数"口径） | 动态排序条形图 | `/rank/top-sellers` |
| | 实时在线榜（60 秒轮询） | 滚动榜单 | `/rank/online-live` |
| | 游戏聚类分群 | 散点图 | `/cluster/games` |
| 右栏·玩家生态 | 好评率分布 | 直方图 | `/ecosystem/rating-dist` |
| | 评论语言分布 | 条形图 | `/ecosystem/review-languages` |
| | 游玩时长分布 | 直方图 | `/ecosystem/playtime-dist` |
| | 评论活跃时段 | 星期 × 小时热力图 | `/ecosystem/activity-heatmap` |
| 详情页 `/game/:appid` | 基本信息、聚类标签、热销预测、情感占比、评论趋势、价格历史、同类对比 | 组合 | `/games/{appid}…` |

## 交互（三层都要做）

1. **全局筛选**：状态集中在 Pinia `stores/filters.ts`；筛选变化时所有可筛选图表重新请求。
2. **图表联动**：点击树图的某个类型 → 写入 `filters.genre` → 其他图表随之过滤；再次点击或点"重置"取消。
3. **下钻**：点击 Top10 条目或聚类散点 → 路由到 `/game/:appid`。

## 图表规范

"可视化效果"占 20%，每个图表组件按此执行：

- 标题旁写明**单位与口径**，如"拥有者（SteamSpy 区间估算中值）"、"时间（UTC）"。
- 类别 > 5 个用条形图或树图；饼图仅用于 ≤ 5 类的占比。
- **三态**：加载中 / 空数据 / 报错，统一由 `BaseChart` 处理；接口失败时提示并保留上次成功的数据作为降级。
- 地域构成用评论语言分布表达，大屏只使用自有数据图表（地图需审图号合规底图，本项目不引入）。
- 颜色、字号、数字格式全部来自 `theme/`，组件内只引用主题。

## 视觉 token（Steam 深色科技蓝）

| token | 值 | 用途 |
|---|---|---|
| `--bg-base` | `#171a21` | 页面底色 |
| `--bg-panel` | `#1b2838` | 面板 |
| `--bg-raised` | `#2a475e` | 边框、悬浮层 |
| `--accent` | `#66c0f4` | 主强调、第一系列 |
| `--text-primary` | `#c7d5e0` | 正文 |
| `--positive` / `--negative` | `#a4d007` / `#c35c2c` | 好评 / 差评 |

ECharts 主题在 `src/theme/steam-dark.ts` 中 `registerTheme`，CSS 变量在 `src/theme/tokens.css`。

## 目录约定

`index.html` 写 `<meta charset="UTF-8">`。

```
src/
  api/              axios 实例（解包 {code,msg,data}，code ≠ 0 抛错）+ 按 docs/api.md 分组的请求函数
  stores/filters.ts 全局筛选状态
  theme/            steam-dark.ts、tokens.css
  components/layout/ScreenContainer.vue   1920×1080 等比缩放容器
  components/charts/BaseChart.vue        init / resize / dispose / 三态
  components/charts/*.vue                每个看板模块一个组件
  views/Dashboard.vue、views/GameDetail.vue
```
