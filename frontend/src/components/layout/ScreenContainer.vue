<script setup lang="ts">
/**
 * 1920×1080 设计稿的等比缩放容器：按窗口宽高取较小的缩放比，居中显示，四周留黑边。
 * 内部所有尺寸都按 1920×1080 写死像素即可，任何分辨率的投屏都不变形。
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'

const W = 1920
const H = 1080
const scale = ref(1)
const offset = ref({ x: 0, y: 0 })

function fit() {
  const s = Math.min(window.innerWidth / W, window.innerHeight / H)
  scale.value = s
  offset.value = { x: (window.innerWidth - W * s) / 2, y: (window.innerHeight - H * s) / 2 }
}

onMounted(() => {
  fit()
  window.addEventListener('resize', fit)
})
onBeforeUnmount(() => window.removeEventListener('resize', fit))
</script>

<template>
  <div class="screen-viewport">
    <div
      class="screen"
      :style="{ transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})` }"
    >
      <slot />
    </div>
  </div>
</template>

<style scoped>
.screen-viewport {
  position: fixed;
  inset: 0;
  overflow: hidden;
  background: var(--bg-base);
}
.screen {
  position: absolute;
  top: 0;
  left: 0;
  width: 1920px;
  height: 1080px;
  transform-origin: 0 0;
  background:
    radial-gradient(ellipse at 50% -10%, rgba(102, 192, 244, 0.12), transparent 55%),
    var(--bg-base);
}
</style>
