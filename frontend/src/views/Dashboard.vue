<script setup lang="ts">
/**
 * 大屏外壳（1920×1080）：顶栏（标签页 + 全局筛选）+ 当前标签页的内容。
 * - 标签页是子路由（/overview、/market、/players、/hits），可以直接用链接打开某一页；
 * - 切换时新页面用 CSS 动画淡入上移（不依赖帧回调）；已打开过的页用 KeepAlive 缓存，切回来不重新请求；
 * - 自动轮播：每页停留 CAROUSEL_SECONDS 秒，手动点标签页即停止；键盘 ← → / 1–4 切换。
 */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import HeaderBar from '@/components/dashboard/HeaderBar.vue'
import ScreenContainer from '@/components/layout/ScreenContainer.vue'

import { CAROUSEL_SECONDS, TABS } from './tabs/registry'

defineOptions({ name: 'Dashboard' })

const route = useRoute()
const router = useRouter()
const autoplay = ref(false)
let timer: ReturnType<typeof setInterval> | null = null

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
    <div class="dashboard">
      <HeaderBar v-model:autoplay="autoplay" @manual-nav="autoplay = false" />
      <main class="content">
        <RouterView v-slot="{ Component }">
          <KeepAlive>
            <component :is="Component" />
          </KeepAlive>
        </RouterView>
      </main>
      <div v-if="autoplay" :key="route.path" class="progress" :style="{ animationDuration: `${CAROUSEL_SECONDS}s` }" />
    </div>
  </ScreenContainer>
</template>

<style scoped>
.dashboard {
  position: relative;
  height: 100%;
  display: flex;
  flex-direction: column;
}
.content {
  flex: 1;
  min-height: 0;
  padding: 20px 32px 28px;
}
/* 切页动效：新页面一插入 DOM 就播放淡入上移（KeepAlive 切回来时重新插入，动画也会重播）。
   不用 <Transition mode="out-in">：它依赖 requestAnimationFrame 推进离场，浏览器在后台或被遮挡时
   会暂停帧回调，旧页卡在离场、新页迟迟不挂载，轮播演示时就会出现空白页。 */
.content > :deep(*) {
  height: 100%;
  animation: tab-in 0.4s ease both;
}
@keyframes tab-in {
  from {
    opacity: 0;
    transform: translateY(14px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}
/* 轮播进度条：贴在底边，跑满一条换下一页 */
.progress {
  position: absolute;
  left: 0;
  bottom: 0;
  height: 3px;
  width: 100%;
  transform-origin: 0 50%;
  background: linear-gradient(90deg, transparent, var(--accent));
  box-shadow: 0 0 10px var(--accent-glow);
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
