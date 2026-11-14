<script setup lang="ts">
/**
 * 所有 ECharts 图表的底座：init / resize / dispose，以及三态（加载中 / 空数据 / 报错）。
 * - 有旧数据时请求失败：继续显示旧图，右上角提示"数据未更新"（降级）；
 * - 没有任何数据时失败：显示错误与"重试"按钮。
 */
import { nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'

import { echarts, type ChartOption } from '@/charts/echarts'
import IconButton from '@/components/layout/IconButton.vue'
import type { RemoteState } from '@/composables/useRemote'
import { THEME_NAME } from '@/theme/steam-dark'

const props = withDefaults(
  defineProps<{
    option: ChartOption | null
    state: RemoteState
    error?: string | null
    empty?: boolean
    emptyText?: string
    /** false = 合并更新，保留过渡动画（动态排序条形图用） */
    notMerge?: boolean
  }>(),
  { error: null, empty: false, emptyText: '暂无数据', notMerge: true },
)

const emit = defineEmits<{
  (e: 'chart-click', params: echarts.ECElementEvent): void
  (e: 'retry'): void
}>()

const el = ref<HTMLDivElement>()
const chart = shallowRef<echarts.ECharts>()
let observer: ResizeObserver | null = null

function render() {
  if (!chart.value || !props.option) return
  chart.value.setOption(props.option, { notMerge: props.notMerge, lazyUpdate: true })
}

// ECharts 画在 canvas 上，首次绘制时如果中文字体分片还没下载完，会先用占位字体画，
// 之后不会自己重画。所以每批字体下载完成后整体重绘一次（不带动画，避免闪动）。
function onFontsLoaded() {
  if (!chart.value || !props.option) return
  chart.value.setOption({ ...props.option, animation: false }, { notMerge: true })
}

onMounted(async () => {
  await nextTick()
  if (!el.value) return
  chart.value = echarts.init(el.value, THEME_NAME, { renderer: 'canvas' })
  chart.value.on('click', (p) => emit('chart-click', p as echarts.ECElementEvent))
  // 侧栏折叠时容器宽度连续变化 0.6 秒，每帧都会触发 resize；关掉 resize 自带的过渡动画，
  // 图表跟着容器实时拉伸，而不是每帧重新播放一次变形动画
  observer = new ResizeObserver(() => chart.value?.resize({ animation: { duration: 0 } }))
  observer.observe(el.value)
  document.fonts?.addEventListener('loadingdone', onFontsLoaded)
  render()
})

watch(() => props.option, render)

onBeforeUnmount(() => {
  document.fonts?.removeEventListener('loadingdone', onFontsLoaded)
  observer?.disconnect()
  chart.value?.dispose()
})

const hasOption = () => props.option !== null && !props.empty
</script>

<template>
  <div class="base-chart">
    <div ref="el" class="canvas" :class="{ hidden: !hasOption() }" />

    <div v-if="state === 'loading' && !hasOption()" class="overlay">
      <span class="spinner" />加载中…
    </div>
    <div v-else-if="state === 'error' && !hasOption()" class="overlay error">
      <span>{{ error || '加载失败' }}</span>
      <IconButton icon="retry" label="重试" :size="42" @click="emit('retry')" />
    </div>
    <div v-else-if="state === 'ready' && empty" class="overlay empty">
      <span class="empty-icon" aria-hidden="true" />
      <span>{{ emptyText }}</span>
    </div>

    <div v-if="state === 'error' && hasOption()" class="stale" :title="error || ''">数据未更新</div>
    <div v-if="state === 'loading' && hasOption()" class="refreshing"><span class="spinner" /></div>
  </div>
</template>

<style scoped>
.base-chart {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 0;
}
.canvas {
  width: 100%;
  height: 100%;
}
.canvas.hidden {
  visibility: hidden;
}
.overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--text-secondary);
  font-size: var(--fs-body);
  text-align: center;
  padding: 0 24px;
}
.overlay.empty {
  flex-direction: column;
  font-size: 18px;
}
/* 空态图标：一个虚线圆环，示意"数据还没生成" */
.empty-icon {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  border: 2px dashed rgba(163, 167, 240, 0.45);
  box-shadow: 0 0 24px rgba(163, 167, 240, 0.15);
  animation: empty-spin 14s linear infinite;
}
.overlay.error {
  color: var(--negative);
  flex-direction: column;
}
.stale {
  position: absolute;
  top: 0;
  right: 0;
  font-size: var(--fs-small);
  color: var(--warning);
  background: rgba(227, 207, 154, 0.12);
  border-radius: 6px;
  padding: 2px 10px;
}
.refreshing {
  position: absolute;
  top: 2px;
  right: 2px;
}
.spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid var(--bg-raised);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes empty-spin {
  to {
    transform: rotate(360deg);
  }
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
