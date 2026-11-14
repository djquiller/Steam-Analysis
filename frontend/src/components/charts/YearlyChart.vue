<script setup lang="ts">
/** 历年发行量（柱）与均价（线），双纵轴共用年份轴 */
import { storeToRefs } from 'pinia'
import { computed } from 'vue'

import { trendApi } from '@/api'
import type { ChartOption } from '@/charts/echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import Panel from '@/components/layout/Panel.vue'
import { useRemote } from '@/composables/useRemote'
import { useFiltersStore } from '@/stores/filters'
import { intNum } from '@/theme/format'
import { barGradient, color } from '@/theme/steam-dark'

const { params } = storeToRefs(useFiltersStore())
const r = useRemote((s) => trendApi.yearly(params.value, s), [params])

const option = computed<ChartOption | null>(() => {
  const d = r.data.value
  if (!d) return null
  return {
    grid: { left: 8, right: 8, top: 56, bottom: 8, containLabel: true },
    legend: { top: 0, left: 'center', data: ['发行量', '均价'] },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      valueFormatter: undefined,
      formatter: (ps: any[]) => {
        const it = d[ps[0]?.dataIndex]
        if (!it) return ''
        return `${it.year} 年<br/>发行量：${intNum(it.game_cnt)} 款<br/>均价：$${(it.avg_price_usd ?? 0).toFixed(2)}（含免费）`
      },
    },
    xAxis: { type: 'category', data: d.map((x) => x.year) },
    yAxis: [
      { type: 'value', name: '款', axisLabel: { formatter: (v: number) => (v >= 1000 ? `${v / 1000}k` : `${v}`) } },
      { type: 'value', name: '美元', splitLine: { show: false } },
    ],
    series: [
      {
        name: '发行量',
        type: 'bar',
        data: d.map((x) => x.game_cnt),
        barMaxWidth: 26,
        itemStyle: { borderRadius: [8, 8, 2, 2], color: barGradient() },
        emphasis: { itemStyle: { color: barGradient(color.accentBright, 0.2) } },
      },
      {
        name: '均价',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        symbol: 'none',
        data: d.map((x) => x.avg_price_usd),
        lineStyle: { color: '#ffffff', width: 2.5, type: [6, 6], shadowColor: 'rgba(212, 214, 255, 0.8)', shadowBlur: 12 },
        itemStyle: { color: '#ffffff' },
      },
    ],
  }
})
</script>

<template>
  <Panel title="历年发行量与均价">
    <BaseChart
      :option="option"
      :state="r.state.value"
      :error="r.error.value"
      :empty="!!r.data.value && r.data.value.length === 0"
      empty-text="当前筛选下没有游戏"
      @retry="r.reload"
    />
  </Panel>
</template>
