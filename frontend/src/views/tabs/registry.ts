// 大屏的标签页：第一页是总览，后三页按答辩讲述顺序排列（市场 → 玩家 → 热销）。
// 名称按页内卡片的实际内容命名（名词短语，不用句子）；hint 列出页内卡片，显示在主区标题的后半段。
// 每页最多 4 张大卡片，避免一屏塞太多小图让观众眼睛疲劳。
export interface TabDef {
  path: string
  name: string
  label: string
  hint: string
}

export const TABS: TabDef[] = [
  { path: '/overview', name: 'overview', label: '总览', hint: '规模与实时在线' },
  { path: '/market', name: 'market', label: '类型与价格', hint: '类型热度 · 价格 × 好评率' },
  { path: '/players', name: 'players', label: '评论与口碑', hint: '好评率 · 语言 · 时长 · 时段' },
  { path: '/hits', name: 'hits', label: '热销与分群', hint: '热销榜 · 聚类' },
]
