<script setup lang="ts">
/**
 * 大屏缩放容器：以 1920×1080 为基准等比缩放，并铺满整个窗口、不留黑边。
 *
 * 缩放比取 min(窗口宽 / 1920, 窗口高 / 1080)，保证字号与卡片按比例放大缩小；
 * 画布尺寸再按窗口比例补齐：
 * - 窗口比 16:9 宽（带鱼屏、浏览器全屏后高度变小）：画布高 1080，宽度大于 1920；
 * - 窗口比 16:9 窄（16:10、4:3 投影）：画布宽 1920，高度大于 1080。
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
      <div class="sheen" aria-hidden="true" />
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
  overflow: hidden;
  /* 深靛黑底 + 右上角一片薰衣草色的天光 + 左下角暗紫光晕，给磨砂卡片一个有纵深的背景 */
  background:
    radial-gradient(ellipse 1100px 700px at 88% -12%, rgba(150, 155, 225, 0.28), transparent 70%),
    radial-gradient(ellipse 900px 800px at -5% 105%, rgba(90, 94, 168, 0.22), transparent 70%),
    radial-gradient(ellipse 700px 500px at 45% 55%, rgba(60, 62, 110, 0.18), transparent 70%),
    linear-gradient(160deg, #11121f 0%, #0b0c16 55%, #0d0e1b 100%);
}
/* 流光：一束很淡的斜向光带缓慢扫过整个背景，周期 18 秒 */
.sheen {
  position: absolute;
  inset: -20%;
  pointer-events: none;
  background: linear-gradient(
    115deg,
    transparent 38%,
    rgba(212, 214, 255, 0.045) 46%,
    rgba(212, 214, 255, 0.085) 50%,
    rgba(212, 214, 255, 0.045) 54%,
    transparent 62%
  );
  background-size: 220% 100%;
  animation: sheen 18s ease-in-out infinite;
}
@keyframes sheen {
  0% {
    background-position: 130% 0;
  }
  100% {
    background-position: -30% 0;
  }
}
</style>
