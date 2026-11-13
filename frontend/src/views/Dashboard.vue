<script setup lang="ts">
/**
 * 大屏外壳：左侧可折叠导航 + 右侧主区（页标题、全局筛选、当前标签页的卡片）。
 * - 标签页是子路由（/overview、/market、/players、/hits），可以直接用链接打开某一页；
 * - 切页时标题和卡片用 CSS 动画依次落位（不依赖帧回调，见下方样式注释）；已打开过的页用 KeepAlive 缓存；
 * - 自动轮播：每页停留 CAROUSEL_SECONDS 秒，手动切页即停止；键盘 ← → / 1–4 切换；
 * - 点左上角 Logo 折叠 / 展开导航（见 SideNav），状态记在浏览器本地，刷新后保持。
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import FilterBar from '@/components/dashboard/FilterBar.vue'
import SideNav from '@/components/dashboard/SideNav.vue'
import ScreenContainer from '@/components/layout/ScreenContainer.vue'

import { CAROUSEL_SECONDS, TABS } from './tabs/registry'

defineOptions({ name: 'Dashboard' })

const route = useRoute()
const router = useRouter()
const autoplay = ref(false)
let timer: ReturnType<typeof setInterval> | null = null

const COLLAPSE_KEY = 'steam-dashboard.nav-collapsed'
function readCollapsed(): boolean {
  try {
    return localStorage.getItem(COLLAPSE_KEY) === '1'
  } catch {
    return false
  }
}
const collapsed = ref(readCollapsed())
watch(collapsed, (v) => {
  try {
    localStorage.setItem(COLLAPSE_KEY, v ? '1' : '0')
  } catch {
    /* 隐私模式等情况下存不了，不影响使用 */
  }
})

const current = computed(() => TABS.find((t) => route.path.startsWith(t.path)) ?? TABS[0]!)

function currentIndex() {
  const i = TABS.findIndex((t) => route.path.startsWith(t.path))
  return i < 0 ? 0 : i
}

function go(offset: number) {
  const next = TABS[(currentIndex() + offset + TABS.length) % TABS.length]
  if (next) router.push(next.path)
}

watch(autoplay, (on) => {
  if (timer) clearInterval(timer)
  timer = on ? setInterval(() => go(1), CAROUSEL_SECONDS * 1000) : null
})

function onKey(e: KeyboardEvent) {
  const el = e.target as HTMLElement | null
  if (el && ['INPUT', 'SELECT', 'TEXTAREA'].includes(el.tagName)) return
  if (e.key === 'ArrowRight') go(1)
  else if (e.key === 'ArrowLeft') go(-1)
  else if (/^[1-9]$/.test(e.key)) {
    const t = TABS[Number(e.key) - 1]
    if (t) router.push(t.path)
  } else return
  autoplay.value = false
}

onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
  if (timer) clearInterval(timer)
})
</script>

<template>
  <ScreenContainer>
    <div class="shell">
      <SideNav v-model:autoplay="autoplay" v-model:collapsed="collapsed" @manual-nav="autoplay = false" />

      <section class="main">
        <header class="head">
          <h1 :key="current.name" class="title">
            {{ current.label }}<span>{{ current.hint }}</span>
          </h1>
        </header>

        <FilterBar class="filter-bar" />

        <main class="content">
          <RouterView v-slot="{ Component }">
            <KeepAlive>
              <component :is="Component" />
            </KeepAlive>
          </RouterView>
        </main>
      </section>

      <div v-if="autoplay" :key="route.path" class="progress" :style="{ animationDuration: `${CAROUSEL_SECONDS}s` }" />
    </div>
  </ScreenContainer>
</template>

<style scoped>
.shell {
  position: relative;
  height: 100%;
  display: flex;
}
.main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  padding: 26px 36px 30px 32px;
}

.head {
  height: 80px;
  flex: none;
  display: flex;
  align-items: center;
  gap: 22px;
}

/* 页标题：标签名白色 + 说明薰衣草色，切页时重新挂载并播放入场动画 */
.title {
  margin: 0;
  font-size: 46px;
  font-weight: 400;
  letter-spacing: 1px;
  color: var(--text-strong);
  white-space: nowrap;
  animation: title-in 0.7s var(--ease-out) backwards;
}
.title span {
  margin-left: 18px;
  color: var(--accent);
  background: linear-gradient(100deg, var(--accent) 20%, var(--accent-bright) 50%, var(--accent) 80%);
  background-size: 250% 100%;
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  /* 流光：一道亮光缓慢扫过说明文字 */
  animation: text-sheen 6s ease-in-out infinite;
}
@keyframes title-in {
  from {
    opacity: 0;
    transform: translateY(10px);
    filter: blur(8px);
  }
}
@keyframes text-sheen {
  0%,
  100% {
    background-position: 100% 0;
  }
  50% {
    background-position: 0% 0;
  }
}

.filter-bar {
  flex: none;
  margin: 10px 0 22px;
  align-self: flex-start;
  min-width: 0;
  max-width: 100%;
}

.content {
  flex: 1;
  min-height: 0;
}
/* 切页动效：卡片一插入 DOM 就播放入场动画，同组卡片按顺序错开（KeepAlive 切回来时重新插入，动画会重播）。
   不用 <Transition mode="out-in">：它依赖 requestAnimationFrame 推进离场，浏览器在后台或被遮挡时
   会暂停帧回调，旧页卡在离场、新页迟迟不挂载，轮播演示时就会出现空白页。
   fill-mode 用 backwards 而不是 both：动画结束后不再锁定 transform，卡片的悬停上浮才能生效。 */
.content > :deep(*) {
  height: 100%;
}
.content :deep(.glass) {
  animation: card-in 0.8s var(--ease-out) backwards;
}
.content :deep(.glass:nth-child(2)) {
  animation-delay: 0.08s;
}
.content :deep(.glass:nth-child(3)) {
  animation-delay: 0.16s;
}
.content :deep(.glass:nth-child(4)) {
  animation-delay: 0.24s;
}

/* 轮播进度条：贴在底边，跑满一条换下一页 */
.progress {
  position: absolute;
  left: 0;
  bottom: 0;
  height: 3px;
  width: 100%;
  transform-origin: 0 50%;
  background: linear-gradient(90deg, transparent, var(--accent-bright));
  box-shadow: 0 0 12px var(--accent-glow);
  animation: progress linear forwards;
}
@keyframes progress {
  from {
    transform: scaleX(0);
  }
  to {
    transform: scaleX(1);
  }
}
</style>
