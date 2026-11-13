import { createRouter, createWebHistory } from 'vue-router'

import Dashboard from '@/views/Dashboard.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: Dashboard },
    {
      path: '/game/:appid(\\d+)',
      name: 'game',
      component: () => import('@/views/GameDetail.vue'),
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})
