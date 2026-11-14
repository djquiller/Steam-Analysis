<script setup lang="ts">
/** 评论语言分布：横向条形图（语言 > 5 种，不用饼图），代替地图表达评论的地域构成 */
import { storeToRefs } from 'pinia'
import { computed } from 'vue'

import { ecosystemApi } from '@/api'
import type { ChartOption } from '@/charts/echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import Panel from '@/components/layout/Panel.vue'
import { useRemote } from '@/composables/useRemote'
import { useFiltersStore } from '@/stores/filters'
import { bigNum, pct } from '@/theme/format'
import { color, font, hbarGradient } from '@/theme/steam-dark'

// Steam 语言代码 → 中文名（只列常见的，其余显示原代码）
const LANG: Record<string, string> = {
  english: '英语', schinese: '简体中文', tchinese: '繁体中文', russian: '俄语', spanish: '西班牙语',
  latam: '拉美西语', brazilian: '巴西葡语', portuguese: '葡萄牙语', german: '德语', french: '法语',
  turkish: '土耳其语', polish: '波兰语', japanese: '日语', koreana: '韩语', italian: '意大利语',
  ukrainian: '乌克兰语', thai: '泰语', czech: '捷克语', other: '其他',
}

const { params } = storeToRefs(useFiltersStore())
const r = useRemote((s) => ecosystemApi.reviewLanguages({ ...params.value, limit: 8 }, s), [params])

const option = computed<ChartOption | null>(() => {
  const d = r.data.value
  if (!d) return null
  return {
    grid: { left: 8, right: 70, top: 8, bottom: 8, containLabel: true },
    tooltip: {
      formatter: (p: any) => {
        const it = d.items[p.dataIndex]
        if (!it) return ''
        return `<b>${LANG[it.language] ?? it.language}</b><br/>评论：${bigNum(it.review_cnt)} 条（${pct(it.share)}）<br/>好评占比：${pct(it.positive_rate)}`
      },
    },
    xAxis: { type: 'value', show: false },
    yAxis: { type: 'category', inverse: true, data: d.items.map((x) => LANG[x.language] ?? x.language) },
    series: [
      {
        type: 'bar',
        barMaxWidth: 28,
        data: d.items.map((x) => x.review_cnt),
        itemStyle: { color: hbarGradient(), borderRadius: [0, 14, 14, 0] },
        label: { show: true, position: 'right', color: color.text, fontSize: font.small, formatter: (p: any) => pct(d.items[p.dataIndex]?.share) },
      },
    ],
  }
})
</script>

<template>
  <Panel title="评论语言分布">
    <BaseChart
      :option="option"
      :state="r.state.value"
      :error="r.error.value"
      :empty="!!r.data.value && r.data.value.items.length === 0"
      empty-text="评论侧聚合尚未运行"
      @retry="r.reload"
    />
  </Panel>
</template>
