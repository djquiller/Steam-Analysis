// 大屏的标签页：第一页是总览，后三页按答辩讲述顺序排列（市场 → 玩家 → 热销）。
// 名称按页内卡片的实际内容命名（名词短语，不用句子）；侧栏标签和主区页标题都显示它。
// 每页最多 4 张大卡片，避免一屏塞太多小图让观众眼睛疲劳。
export interface TabDef {
  path: string
  name: string
  label: string
}

export const TABS: TabDef[] = [
  { path: '/overview', name: 'overview', label: '总览' },
  { path: '/market', name: 'market', label: '类型与价格' },
  { path: '/players', name: 'players', label: '评论与口碑' },
  { path: '/hits', name: 'hits', label: '热销与分群' },
]
