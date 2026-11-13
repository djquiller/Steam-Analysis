// 大屏的标签页：按故事线"市场在变 → 玩家在想什么 → 什么游戏会火"排列，第一页是总览。
// 每页最多 4 张大卡片，避免一屏塞太多小图让观众眼睛疲劳。
export interface TabDef {
  path: string
  name: string
  label: string
  hint: string
}

export const TABS: TabDef[] = [
  { path: '/overview', name: 'overview', label: '总览', hint: '规模与实时动态' },
  { path: '/market', name: 'market', label: '市场在变', hint: '类型与价格' },
  { path: '/players', name: 'players', label: '玩家在想什么', hint: '口碑与行为' },
  { path: '/hits', name: 'hits', label: '什么游戏会火', hint: '热销与分群' },
]
