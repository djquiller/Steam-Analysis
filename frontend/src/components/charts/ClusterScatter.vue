<script setup lang="ts">
/** 游戏聚类散点：PCA 二维坐标，颜色 = 所属簇；点击散点下钻详情页 */
import { storeToRefs } from 'pinia'
import { computed } from 'vue'
import { useRouter } from 'vue-router'

import { clusterApi } from '@/api'
import type { ChartOption } from '@/charts/echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import Panel from '@/components/layout/Panel.vue'
import { useRemote } from '@/composables/useRemote'
import { useFiltersStore } from '@/stores/filters'
import { bigNum, intNum, pct, usd } from '@/theme/format'
import { palette } from '@/theme/steam-dark'

const router = useRouter()
const { params } = storeToRefs(useFiltersStore())
const r = useRemote((s) => clusterApi.games({ ...params.value, limit: 3000 }, s), [params])

const option = computed<ChartOption | null>(() => {
  const d = r.data.value
  if (!d) return null
  return {
    grid: { left: 16, right: 16, top: 30, bottom: 16 },
    legend: { top: 0, data: d.clusters.map((c) => `${c.cluster_label}（${intNum(c.game_cnt)}）`) },
    tooltip: {
      formatter: (p: any) => {
        const pt = p.data.raw
        return `<b>${pt.name}</b><br/>价格：${usd(pt.price_usd)}<br/>好评率：${pct(pt.positive_rate)}<br/>拥有者：${bigNum(pt.owners_mid)} 份`
      },
    },
    xAxis: { type: 'value', scale: true, axisLabel: { show: false }, splitLine: { show: false } },
    yAxis: { type: 'value', scale: true, axisLabel: { show: false }, splitLine: { show: false } },
    series: d.clusters.map((c, i) => ({
      name: `${c.cluster_label}（${intNum(c.game_cnt)}）`,
      type: 'scatter',
      symbolSize: 5,
      large: true,
      itemStyle: { color: palette[i % palette.length], opacity: 0.75 },
      data: d.points.filter((p) => p.cluster_id === c.cluster_id).map((p) => ({ value: [p.x, p.y], raw: p })),
    })),
  }
})

function onClick(p: { data?: unknown }) {
  const appid = (p.data as { raw?: { appid: number } } | undefined)?.raw?.appid
  if (appid) router.push(`/game/${appid}`)
}
</script>

<template>
  <Panel
    title="游戏聚类分群"
    :note="`PCA 二维投影（无单位）· 仅评论数 ≥ 10 的游戏${r.data.value?.total ? ` · 共 ${intNum(r.data.value.total)} 款，显示 ${intNum(r.data.value.points.length)} 个点` : ''}`"
  >
    <BaseChart
      :option="option"
      :state="r.state.value"
      :error="r.error.value"
      :empty="!!r.data.value && r.data.value.total === 0"
      empty-text="聚类模型尚未运行"
      @retry="r.reload"
      @chart-click="onClick"
    />
  </Panel>
</template>
