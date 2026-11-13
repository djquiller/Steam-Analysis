import { createRouter, createWebHistory } from 'vue-router'

import Dashboard from '@/views/Dashboard.vue'
import { TABS } from '@/views/tabs/registry'
import HitsTab from '@/views/tabs/HitsTab.vue'
import MarketTab from '@/views/tabs/MarketTab.vue'
import OverviewTab from '@/views/tabs/OverviewTab.vue'
import PlayersTab from '@/views/tabs/PlayersTab.vue'

const tabComponents = { overview: OverviewTab, market: MarketTab, players: PlayersTab, hits: HitsTab }

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: Dashboard,
      redirect: '/overview',
      // 标签页是大屏的子路由：外壳（顶栏、筛选）不动，只换内容区
      children: TABS.map((t) => ({
        path: t.path.slice(1),
        name: t.name,
        component: tabComponents[t.name as keyof typeof tabComponents],
      })),
    },
    {
      path: '/game/:appid(\\d+)',
      name: 'game',
      component: () => import('@/views/GameDetail.vue'),
    },
    { path: '/:pathMatch(.*)*', redirect: '/overview' },
  ],
})
