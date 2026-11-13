<script setup lang="ts">
/**
 * 大屏缩放容器：以 1920×1080 为基准等比缩放，并铺满整个窗口、不留黑边。
 *
 * 缩放比取 min(窗口宽 / 1920, 窗口高 / 1080)，保证字号与卡片按比例放大缩小；
 * 画布尺寸再按窗口比例补齐：
 * - 窗口比 16:9 宽（带鱼屏、浏览器全屏后高度变小）：画布高 1080，宽度大于 1920；
 * - 窗口比 16:9 窄（4:3 投影）：画布宽 1920，高度大于 1080。
 * 内部布局都是 grid / flex，多出来的宽高由卡片分掉，所以写样式时按"至少 1920×1080"来设计。
 */
import { onBeforeUnmount, onMounted, ref } from 'vue'

const BASE_W = 1920
const BASE_H = 1080
const scale = ref(1)
const size = ref({ w: BASE_W, h: BASE_H })

function fit() {
  const vw = window.innerWidth
  const vh = window.innerHeight
  const s = Math.min(vw / BASE_W, vh / BASE_H)
  scale.value = s
  size.value = { w: vw / s, h: vh / s }
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
      :style="{ width: `${size.w}px`, height: `${size.h}px`, transform: `scale(${scale})` }"
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
  transform-origin: 0 0;
  /* 深青黑底 + 几团柔和的光晕 + 极淡的点阵，给玻璃卡片一个有纵深的背景 */
  background:
    radial-gradient(ellipse 900px 600px at 12% 8%, rgba(102, 192, 244, 0.16), transparent 70%),
    radial-gradient(ellipse 800px 700px at 92% 85%, rgba(38, 166, 154, 0.14), transparent 70%),
    radial-gradient(ellipse 600px 500px at 70% 20%, rgba(224, 94, 168, 0.07), transparent 70%),
    radial-gradient(circle, rgba(255, 255, 255, 0.045) 1px, transparent 1.5px) 0 0 / 28px 28px,
    var(--bg-base);
}
</style>
