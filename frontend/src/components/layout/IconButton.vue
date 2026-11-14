<script setup lang="ts">
/**
 * 圆形磨砂图标按钮：按钮上只放矢量图标，不放文字。
 * label 不显示在界面上，只作为 aria-label（读屏）和悬停提示（title），保证不看文字也知道按钮干什么。
 * 每个图标有自己的悬停小动作：返回向左轻推、重试转一圈、重置逆时针回拨。
 * 其他属性（@click、disabled 等）原样透传给 <button>。
 */
defineProps<{ icon: 'back' | 'retry' | 'reset'; label: string; size?: number }>()

// 24×24 线条图标，描边用 currentColor
const PATHS: Record<string, string> = {
  back: 'M19 12H5M11 18l-6-6 6-6',
  retry: 'M20 12a8 8 0 1 1-2.34-5.66M20 4v5h-5',
  reset: 'M4 12a8 8 0 1 0 2.34-5.66M4 4v5h5',
}
</script>

<template>
  <button
    class="icon-btn"
    :class="`icon-${icon}`"
    :aria-label="label"
    :title="label"
    :style="size ? { width: `${size}px`, height: `${size}px` } : undefined"
  >
    <svg viewBox="0 0 24 24" aria-hidden="true"><path :d="PATHS[icon]" /></svg>
  </button>
</template>

<style scoped>
.icon-btn {
  width: 46px;
  height: 46px;
  flex: none;
  display: inline-grid;
  place-items: center;
  padding: 0;
  border-radius: 50%;
  color: var(--text-primary);
  cursor: pointer;
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.09), rgba(255, 255, 255, 0.02));
  border: 1px solid rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(16px);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
  transition:
    border-color 0.35s var(--ease-out),
    color 0.35s var(--ease-out),
    box-shadow 0.35s var(--ease-out),
    opacity 0.35s var(--ease-out),
    transform 0.35s var(--ease-spring);
}
.icon-btn:hover:not(:disabled) {
  color: var(--text-strong);
  border-color: rgba(212, 214, 255, 0.45);
  box-shadow:
    0 0 18px rgba(163, 167, 240, 0.35),
    inset 0 1px 0 rgba(255, 255, 255, 0.1);
}
.icon-btn:active:not(:disabled) {
  transform: scale(0.9);
}
.icon-btn:focus-visible {
  outline: 2px solid var(--accent-bright);
  outline-offset: 3px;
}
.icon-btn:disabled {
  opacity: 0.3;
  cursor: default;
}
svg {
  width: 45%;
  height: 45%;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
  transition: transform 0.55s var(--ease-spring);
}
.icon-back:hover:not(:disabled) svg {
  transform: translateX(-3px);
}
.icon-retry:hover:not(:disabled) svg {
  transform: rotate(360deg);
}
.icon-reset:hover:not(:disabled) svg {
  transform: rotate(-200deg);
}
</style>
