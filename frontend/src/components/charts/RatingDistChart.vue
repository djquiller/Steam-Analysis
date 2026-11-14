<script setup lang="ts">
/** 好评率分布直方图，可切换分箱宽度；颜色从差评色渐变到好评色 */
import { storeToRefs } from 'pinia'
import { computed, ref } from 'vue'

import { ecosystemApi } from '@/api'
import type { ChartOption } from '@/charts/echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import Panel from '@/components/layout/Panel.vue'
import Segmented from '@/components/layout/Segmented.vue'
import { useRemote } from '@/composables/useRemote'
import { useFiltersStore } from '@/stores/filters'
import { intNum } from '@/theme/format'
import { sequential } from '@/theme/steam-dark'

const { params } = storeToRefs(useFiltersStore())
const binWidth = ref(5)
const r = useRemote((s) => ecosystemApi.ratingDist({ ...params.value, bin_width: binWidth.value }, s), [params, binWidth])

const option = computed<ChartOption | null>(() => {
  const d = r.data.value
  if (!d) return null
  return {
    grid: { left: 8, right: 16, top: 30, bottom: 8, containLabel: true },
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
      inRange: { color: sequential.slice(1) },
    },
    series: [{ type: 'bar', barCategoryGap: '14%', itemStyle: { borderRadius: [8, 8, 2, 2] }, data: d.bins.map((b, i) => [i, b.game_cnt]) }],
  }
})
</script>

<template>
  <Panel title="好评率分布">
    <template #actions>
      <Segmented v-model="binWidth" :options="[{ value: 5, label: '5%' }, { value: 10, label: '10%' }]" />
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

