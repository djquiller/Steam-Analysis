<script setup lang="ts">
/** 写评论时的游玩时长分布：近似对数的 11 个固定分箱 */
import { storeToRefs } from 'pinia'
import { computed } from 'vue'

import { ecosystemApi } from '@/api'
import type { ChartOption } from '@/charts/echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import Panel from '@/components/layout/Panel.vue'
import { useRemote } from '@/composables/useRemote'
import { useFiltersStore } from '@/stores/filters'
import { bigNum, pct } from '@/theme/format'
import { color } from '@/theme/steam-dark'

const { params } = storeToRefs(useFiltersStore())
const r = useRemote((s) => ecosystemApi.playtimeDist(params.value, s), [params])

const label = (lo: number, hi: number | null) => (hi === null ? `${lo}h+` : `${lo}–${hi}h`)

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
        return `游玩 ${label(b.min_hours, b.max_hours)}<br/>${bigNum(b.review_cnt)} 条评论（${pct(d.review_cnt ? b.review_cnt / d.review_cnt : null)}）`
      },
    },
    xAxis: { type: 'category', data: d.bins.map((b) => label(b.min_hours, b.max_hours)), axisLabel: { fontSize: 10, interval: 0 } },
    yAxis: { type: 'value', name: '条', axisLabel: { formatter: (v: number) => bigNum(v, 0) } },
    series: [
      {
        type: 'bar',
        barCategoryGap: '12%',
        data: d.bins.map((b) => b.review_cnt),
        itemStyle: { color: color.positive, opacity: 0.85, borderRadius: [2, 2, 0, 0] },
      },
    ],
  }
})
</script>

<template>
  <Panel title="游玩时长分布" note="写评论时的累计游玩时长（小时，对数分箱）· 评论数（条）">
    <BaseChart
      :option="option"
      :state="r.state.value"
      :error="r.error.value"
      :empty="!!r.data.value && r.data.value.review_cnt === 0"
      empty-text="评论侧聚合尚未运行"
      @retry="r.reload"
    />
  </Panel>
</template>
