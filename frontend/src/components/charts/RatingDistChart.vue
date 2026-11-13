<script setup lang="ts">
/** 好评率分布直方图，可切换分箱宽度；颜色从差评色渐变到好评色 */
import { storeToRefs } from 'pinia'
import { computed, ref } from 'vue'

import { ecosystemApi } from '@/api'
import type { ChartOption } from '@/charts/echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import Panel from '@/components/layout/Panel.vue'
import { useRemote } from '@/composables/useRemote'
import { useFiltersStore } from '@/stores/filters'
import { intNum } from '@/theme/format'
import { color } from '@/theme/steam-dark'

const { params } = storeToRefs(useFiltersStore())
const binWidth = ref(5)
const r = useRemote((s) => ecosystemApi.ratingDist({ ...params.value, bin_width: binWidth.value }, s), [params, binWidth])

const option = computed<ChartOption | null>(() => {
  const d = r.data.value
  if (!d) return null
  return {
    grid: { left: 44, right: 10, top: 14, bottom: 22 },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (ps: any[]) => {
        const b = d.bins[ps[0]?.dataIndex]
        if (!b) return ''
        const share = d.game_cnt ? ((b.game_cnt / d.game_cnt) * 100).toFixed(1) : '0'
        return `好评率 ${b.bin_start}%–${b.bin_end}%<br/>${intNum(b.game_cnt)} 款（${share}%）`
      },
    },
    xAxis: { type: 'category', data: d.bins.map((b) => b.bin_start), axisLabel: { formatter: '{value}%' } },
    yAxis: { type: 'value', name: '款' },
    visualMap: {
      show: false,
      dimension: 0,
      min: 0,
      max: d.bins.length - 1,
      inRange: { color: [color.negative, color.warning, color.positive] },
    },
    series: [{ type: 'bar', barCategoryGap: '8%', data: d.bins.map((b, i) => [i, b.game_cnt]) }],
  }
})
</script>

<template>
  <Panel title="好评率分布" :note="`游戏数（款）· 仅评论数 ≥ 10 的 ${intNum(r.data.value?.game_cnt)} 款`">
    <template #actions>
      <button v-for="w in [5, 10]" :key="w" class="seg" :class="{ on: binWidth === w }" @click="binWidth = w">
        {{ w }}%
      </button>
    </template>
    <BaseChart
      :option="option"
      :state="r.state.value"
      :error="r.error.value"
      :empty="!!r.data.value && r.data.value.game_cnt === 0"
      empty-text="当前筛选下没有评论数 ≥ 10 的游戏"
      @retry="r.reload"
    />
  </Panel>
</template>

<style scoped>
.seg {
  background: transparent;
  border: 1px solid var(--bg-raised);
  color: var(--text-secondary);
  font-size: 11px;
  padding: 0 8px;
  border-radius: 3px;
  cursor: pointer;
}
.seg.on {
  border-color: var(--accent);
  color: var(--accent);
}
</style>
