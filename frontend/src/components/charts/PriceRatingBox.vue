<script setup lang="ts">
/** 价格区间 × 好评率箱线图：五数由后端从 1% 分箱推算 */
import { storeToRefs } from 'pinia'
import { computed } from 'vue'

import { trendApi } from '@/api'
import type { ChartOption } from '@/charts/echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import Panel from '@/components/layout/Panel.vue'
import { useRemote } from '@/composables/useRemote'
import { useFiltersStore } from '@/stores/filters'
import { intNum } from '@/theme/format'
import { color, priceBucketMeta } from '@/theme/steam-dark'

const { params } = storeToRefs(useFiltersStore())
const r = useRemote((s) => trendApi.priceRating(params.value, s), [params])

const option = computed<ChartOption | null>(() => {
  const d = r.data.value
  if (!d) return null
  return {
    grid: { left: 40, right: 16, top: 16, bottom: 24 },
    tooltip: {
      formatter: (p: any) => {
        const it = d[p.dataIndex]
        if (!it) return ''
        return `<b>${priceBucketMeta[it.price_bucket].label}</b>（${intNum(it.game_cnt)} 款）<br/>最大：${it.max}%<br/>上四分位：${it.q3}%<br/>中位数：${it.median}%<br/>下四分位：${it.q1}%<br/>最小：${it.min}%`
      },
    },
    xAxis: { type: 'category', data: d.map((x) => priceBucketMeta[x.price_bucket].label) },
    yAxis: { type: 'value', min: 0, max: 100, name: '%', axisLabel: { formatter: '{value}' } },
    series: [
      {
        type: 'boxplot',
        boxWidth: ['30%', '55%'],
        data: d.map((x) => ({
          value: [x.min, x.q1, x.median, x.q3, x.max],
          itemStyle: { color: 'rgba(102,192,244,0.18)', borderColor: priceBucketMeta[x.price_bucket].color, borderWidth: 1.5 },
        })),
      },
    ],
    color: [color.accent],
  }
})
</script>

<template>
  <Panel title="价格区间 × 好评率" note="好评率（%，1% 分箱推算五数）· 仅评论数 ≥ 10 的游戏">
    <BaseChart
      :option="option"
      :state="r.state.value"
      :error="r.error.value"
      :empty="!!r.data.value && r.data.value.length === 0"
      empty-text="当前筛选下没有评论数 ≥ 10 的游戏"
      @retry="r.reload"
    />
  </Panel>
</template>
