<script setup lang="ts">
/**
 * 胶囊按钮 + 磨砂弹出面板（参考稿里 "4 Casinos ⌄" 那种筛选胶囊）。
 * - 胶囊上显示：名称、当前值，可选一个数字角标；有筛选值时胶囊高亮；
 * - 点击展开面板，再点、点面板外或按 Esc 收起；
 * - 展开用 CSS transition（缩放 + 位移 + 去模糊，带回弹的缓动），面板始终挂在 DOM 上只切 class，
 *   不依赖 requestAnimationFrame，浏览器被遮挡时也不会卡住。
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'

defineProps<{ label: string; value: string; badge?: number; active?: boolean }>()

const open = ref(false)
const root = ref<HTMLElement>()

function onPointerDown(e: PointerEvent) {
  if (open.value && root.value && !root.value.contains(e.target as Node)) open.value = false
}
function onKey(e: KeyboardEvent) {
  if (open.value && e.key === 'Escape') open.value = false
}

onMounted(() => {
  document.addEventListener('pointerdown', onPointerDown)
  document.addEventListener('keydown', onKey)
})
onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', onPointerDown)
  document.removeEventListener('keydown', onKey)
})
</script>

<template>
  <div ref="root" class="pill-popover" :class="{ open }">
    <button class="pill" :class="{ active }" :aria-expanded="open" @click="open = !open">
      <span v-if="badge" class="badge">{{ badge }}</span>
      <span class="label">{{ label }}</span>
      <span class="value">{{ value }}</span>
      <svg class="chev" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9l6 6 6-6" /></svg>
    </button>
    <div class="panel" role="dialog" :aria-hidden="!open">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.pill-popover {
  position: relative;
}
.pill {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 46px;
  padding: 0 16px 0 18px;
  border-radius: 23px;
  color: var(--text-secondary);
  font-size: var(--fs-body);
  cursor: pointer;
  white-space: nowrap;
  background: linear-gradient(110deg, rgba(255, 255, 255, 0.06), rgba(255, 255, 255, 0.015));
  border: 1px solid rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(16px);
  transition:
    border-color 0.35s var(--ease-out),
    background 0.35s var(--ease-out),
    transform 0.35s var(--ease-spring);
}
.pill:hover,
.open .pill {
  border-color: rgba(212, 214, 255, 0.35);
}
.pill:active {
  transform: scale(0.96);
}
.pill.active {
  border-color: rgba(212, 214, 255, 0.45);
  background: linear-gradient(110deg, rgba(163, 167, 240, 0.26), rgba(163, 167, 240, 0.06));
}
.value {
  color: var(--text-primary);
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
}
.badge {
  min-width: 26px;
  height: 26px;
  padding: 0 8px;
  display: grid;
  place-items: center;
  border-radius: 13px;
  font-family: var(--font-number);
  font-size: var(--fs-small);
  color: #16172a;
  background: var(--accent-bright);
  box-shadow: 0 0 12px rgba(163, 167, 240, 0.5);
}
.chev {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
  transition: transform 0.5s var(--ease-spring);
}
.open .chev {
  transform: rotate(180deg);
}

/* 弹出面板：磨砂玻璃，从胶囊下方带回弹地展开 */
.panel {
  position: absolute;
  top: calc(100% + 12px);
  right: 0;
  z-index: 40;
  min-width: 100%;
  padding: 16px;
  border-radius: 18px;
  background:
    linear-gradient(165deg, rgba(255, 255, 255, 0.07), transparent 45%),
    rgba(26, 27, 46, 0.82);
  border: 1px solid rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(24px) saturate(140%);
  box-shadow:
    0 24px 60px rgba(0, 0, 0, 0.5),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);
  transform-origin: top right;
  opacity: 0;
  visibility: hidden;
  transform: translateY(-8px) scale(0.94);
  filter: blur(4px);
  transition:
    opacity 0.25s var(--ease-out),
    transform 0.45s var(--ease-spring),
    filter 0.3s var(--ease-out),
    visibility 0s linear 0.45s;
}
.open .panel {
  opacity: 1;
  visibility: visible;
  transform: none;
  filter: none;
  transition:
    opacity 0.25s var(--ease-out),
    transform 0.45s var(--ease-spring),
    filter 0.3s var(--ease-out),
    visibility 0s;
}
</style>
