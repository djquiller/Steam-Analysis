<script setup lang="ts">
/** 评论活跃时段：星期 × 小时热力图，时间一律 UTC */
import { storeToRefs } from 'pinia'
import { computed } from 'vue'

import { ecosystemApi } from '@/api'
import type { ChartOption } from '@/charts/echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import Panel from '@/components/layout/Panel.vue'
import { useRemote } from '@/composables/useRemote'
import { useFiltersStore } from '@/stores/filters'
import { bigNum, WEEKDAYS } from '@/theme/format'
import { color, font } from '@/theme/steam-dark'

const { params } = storeToRefs(useFiltersStore())
const r = useRemote((s) => ecosystemApi.activityHeatmap(params.value, s), [params])

const option = computed<ChartOption | null>(() => {
  const d = r.data.value
  if (!d) return null
  return {
    grid: { left: 8, right: 16, top: 8, bottom: 48, containLabel: true },
    tooltip: {
      formatter: (p: any) => {
        const [h, w, v] = p.value
        return `${WEEKDAYS[w]} ${h}:00–${h + 1}:00（UTC）<br/>${bigNum(v)} 条评论`
      },
    },
    xAxis: { type: 'category', data: Array.from({ length: 24 }, (_, i) => i), axisLabel: { interval: 2, fontSize: font.small } },
    yAxis: { type: 'category', data: WEEKDAYS, inverse: true },
    visualMap: {
      min: 0,
      max: d.max_cnt || 1,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      itemHeight: 200,
      itemWidth: 12,
      calculable: false,
      text: ['多', '少'],
      inRange: { color: [color.bgPanel, '#2a5a7a', color.accent, '#d6f0ff'] },
    },
    series: [
      {
        type: 'heatmap',
        data: d.cells.map((c) => [c.hour, c.weekday, c.review_cnt]),
        itemStyle: { borderColor: color.bgPanel, borderWidth: 1 },
        emphasis: { itemStyle: { borderColor: '#fff' } },
      },
    ],
  }
})
</script>

<template>
  <Panel title="评论活跃时段" note="星期 × 小时 · 时间（UTC）· 评论数（条）">
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
