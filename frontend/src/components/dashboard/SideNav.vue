<script setup lang="ts">
/**
 * 左侧可折叠导航：品牌 · 四个标签页。
 * - 展开 304px：图标 + 标签名；折叠 92px：只剩图标，悬停用浏览器原生提示看名字。
 * - 当前页的高亮块是一个独立的层，切页时沿竖直方向弹性滑到新位置，而不是闪一下。
 * - 左上角的 Logo 就是折叠开关：悬停时弹性摆正、放大并扫过一道光；按下压缩，松开后果冻式回弹。
 * 文字与按钮都沿用改版前顶栏里的那些，没有新增。
 */
import { computed, ref } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

import { TABS } from '@/views/tabs/registry'

const collapsed = defineModel<boolean>('collapsed', { required: true })

const route = useRoute()

// 点击 Logo：切换折叠，并重播一次回弹动画。
// 先去掉 class、读一次 offsetWidth 强制浏览器结算样式，再加回去，动画才会从头播放
// （不用 requestAnimationFrame，浏览器被遮挡时帧回调会暂停）。
const logo = ref<HTMLButtonElement>()
function onLogo() {
  collapsed.value = !collapsed.value
  const el = logo.value
  if (!el) return
  el.classList.remove('pop')
  void el.offsetWidth
  el.classList.add('pop')
}

const ITEM_H = 56
const ITEM_GAP = 10
const activeIndex = computed(() => TABS.findIndex((t) => route.path.startsWith(t.path)))

// 每个标签页一个线条图标（24×24，描边用 currentColor，随文字颜色变化）
const ICONS: Record<string, string> = {
  overview: 'M4 4h7v7H4zM13 4h7v4h-7zM13 10h7v10h-7zM4 13h7v7H4z',
  market: 'M3 17l5-5 4 4 8-9M15 7h5v5',
  players: 'M8 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zM2.5 20c.6-3.3 2.8-5 5.5-5s4.9 1.7 5.5 5M16 11a3 3 0 1 0 0-6M18 15c2 .5 3.2 2 3.5 5',
  hits: 'M12 3c1 3.5 5 5.5 5 10a5 5 0 0 1-10 0c0-2 1-3.5 2-4.5.3 1.5 1 2.5 2 3 0-3-.5-5.5 1-8.5z',
}
</script>

<template>
  <aside class="side" :class="{ collapsed }">
    <div class="brand">
      <button
        ref="logo"
        class="logo"
        :aria-label="collapsed ? '展开导航' : '折叠导航'"
        :aria-expanded="!collapsed"
        @click="onLogo"
        @animationend="logo?.classList.remove('pop')"
      />
      <div class="brand-text">
        <div class="name">Steam Analysis</div>
      </div>
    </div>

    <nav class="nav" :style="{ '--item-h': `${ITEM_H}px`, '--item-gap': `${ITEM_GAP}px` }">
      <div
        v-if="activeIndex >= 0"
        class="indicator"
        :style="{ transform: `translateY(${activeIndex * (ITEM_H + ITEM_GAP)}px)` }"
      />
      <RouterLink
        v-for="t in TABS"
        :key="t.name"
        :to="t.path"
        class="item"
        active-class="on"
        :title="collapsed ? t.label : undefined"
      >
        <svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path :d="ICONS[t.name]" /></svg>
        <span class="text label">{{ t.label }}</span>
      </RouterLink>
    </nav>

  </aside>
</template>

<style scoped>
.side {
  --w: 304px;
  width: var(--w);
  flex: none;
  display: flex;
  flex-direction: column;
  gap: 36px;
  padding: 30px 18px 26px;
  overflow: hidden;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.025), rgba(255, 255, 255, 0.01));
  border-right: 1px solid rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(18px);
  transition:
    width 0.6s var(--ease-out),
    padding 0.6s var(--ease-out);
}
.side.collapsed {
  --w: 92px;
  padding-left: 14px;
  padding-right: 14px;
}

/* 折叠时文字淡出并收起；展开时稍晚淡入，等宽度先打开 */
.text,
.brand-text {
  white-space: nowrap;
  transition:
    opacity 0.35s var(--ease-out) 0.15s,
    transform 0.45s var(--ease-out) 0.1s;
}
.collapsed .text,
.collapsed .brand-text {
  opacity: 0;
  transform: translateX(-8px);
  pointer-events: none;
  transition-delay: 0s;
}

.brand {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 0 6px;
  min-height: 48px;
}
.collapsed .brand {
  padding: 0 12px;
}
/* Logo = 折叠开关。静止时微微倾斜；悬停弹性摆正放大（缓动带过冲）；按下快速压缩；点击后播放果冻回弹 */
.logo {
  position: relative;
  overflow: hidden;
  width: 40px;
  height: 40px;
  flex: none;
  padding: 0;
  border: 0;
  border-radius: 12px;
  cursor: pointer;
  background:
    radial-gradient(circle at 30% 25%, #ffffff, transparent 45%),
    linear-gradient(140deg, #d4d6ff, #7f84dc 55%, #2c2e4a);
  box-shadow:
    0 0 24px rgba(163, 167, 240, 0.45),
    inset 0 1px 0 rgba(255, 255, 255, 0.6);
  transform: rotate(-8deg);
  transition:
    transform 0.7s var(--ease-spring),
    box-shadow 0.5s var(--ease-out),
    border-radius 0.5s var(--ease-out);
}
/* 悬停时一道高光从左上斜扫到右下 */
.logo::after {
  content: '';
  position: absolute;
  inset: -50%;
  background: linear-gradient(120deg, transparent 40%, rgba(255, 255, 255, 0.85) 50%, transparent 60%);
  transform: translate(-60%, -60%);
  transition: transform 0.9s var(--ease-out);
  pointer-events: none;
}
.logo:hover {
  transform: rotate(0deg) scale(1.12);
  border-radius: 14px;
  box-shadow:
    0 0 40px rgba(163, 167, 240, 0.75),
    0 0 0 4px rgba(163, 167, 240, 0.12),
    inset 0 1px 0 rgba(255, 255, 255, 0.7);
}
.logo:hover::after {
  transform: translate(60%, 60%);
}
.logo:active {
  transform: rotate(-14deg) scale(0.86);
  transition-duration: 0.15s;
  transition-timing-function: cubic-bezier(0.4, 0, 1, 1);
}
.logo:focus-visible {
  outline: 2px solid var(--accent-bright);
  outline-offset: 4px;
}
.logo.pop {
  animation: logo-pop 0.75s var(--ease-out);
}
@keyframes logo-pop {
  0% {
    transform: rotate(-14deg) scale(0.86);
  }
  35% {
    transform: rotate(10deg) scale(1.22, 1.02);
  }
  55% {
    transform: rotate(-6deg) scale(0.96, 1.12);
  }
  75% {
    transform: rotate(3deg) scale(1.08, 1.02);
  }
  100% {
    transform: rotate(0deg) scale(1.12);
  }
}
.brand-text .name {
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 0.5px;
  color: var(--text-strong);
}

.nav {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: var(--item-gap);
}
/* 当前页高亮块：磨砂底 + 左侧一道亮光，弹性滑动到当前项 */
.indicator {
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  height: var(--item-h);
  border-radius: 16px;
  background: linear-gradient(110deg, rgba(163, 167, 240, 0.26), rgba(163, 167, 240, 0.06));
  box-shadow:
    inset 0 0 0 1px rgba(212, 214, 255, 0.18),
    0 10px 30px rgba(10, 10, 30, 0.45);
  transition: transform 0.65s var(--ease-spring);
}
.indicator::before {
  content: '';
  position: absolute;
  left: -18px;
  top: 14px;
  bottom: 14px;
  width: 3px;
  border-radius: 3px;
  background: var(--accent-bright);
  box-shadow: 0 0 14px var(--accent);
}
.item {
  position: relative;
  height: var(--item-h);
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 18px;
  border-radius: 16px;
  color: var(--text-secondary);
  text-decoration: none;
  transition:
    color 0.35s var(--ease-out),
    background 0.35s var(--ease-out);
}
.collapsed .item {
  padding: 0 20px;
}
.item:hover {
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.03);
}
.item.on {
  color: var(--text-strong);
}
.icon {
  width: 24px;
  height: 24px;
  flex: none;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.6;
  stroke-linecap: round;
  stroke-linejoin: round;
  transition: transform 0.45s var(--ease-spring);
}
.item:hover .icon {
  transform: translateX(2px) scale(1.06);
}
.item.on .icon {
  stroke: var(--accent-bright);
  filter: drop-shadow(0 0 6px rgba(163, 167, 240, 0.6));
}
.label {
  font-size: 18px;
  font-weight: 600;
}

</style>
