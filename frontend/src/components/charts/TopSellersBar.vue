<script setup lang="ts">
/**
 * 热销 Top10 动态排序条形图：切换"拥有者 / 在线人数"口径时条形按新顺序动画重排。
 * 下钻：点击条形进入 /game/:appid。
 */
import { storeToRefs } from 'pinia'
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import { rankApi } from '@/api'
import type { TopMetric } from '@/api/types'
import type { ChartOption } from '@/charts/echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import Panel from '@/components/layout/Panel.vue'
import { useRemote } from '@/composables/useRemote'
import { useFiltersStore } from '@/stores/filters'
import { bigNum, dateTime, intNum, pct, usd } from '@/theme/format'
import { color } from '@/theme/steam-dark'

const router = useRouter()
const { params } = storeToRefs(useFiltersStore())
const metric = ref<TopMetric>('owners')
const r = useRemote((s) => rankApi.topSellers({ ...params.value, metric: metric.value, limit: 10 }, s), [params, metric])

const NOTE: Record<TopMetric, string> = {
  owners: '拥有者（份，SteamSpy 区间估算中值）· 点击查看详情',
  ccu: '最新在线人数（人，每小时采集）· 点击查看详情',
}

const option = computed<ChartOption | null>(() => {
  const d = r.data.value
  if (!d) return null
  const val = (x: (typeof d)[number]) => (metric.value === 'owners' ? x.owners_mid : x.ccu_latest) ?? 0
  return {
    grid: { left: 8, right: 70, top: 6, bottom: 6, containLabel: true },
    tooltip: {
      formatter: (p: any) => {
        const it = d[p.dataIndex]
        if (!it) return ''
        return `<b>${it.name}</b>（${it.release_year}）<br/>价格：${usd(it.price_usd)}<br/>拥有者：${bigNum(it.owners_mid)} 份<br/>最新在线：${intNum(it.ccu_latest)} 人${it.ccu_at ? `（${dateTime(it.ccu_at)}）` : ''}<br/>历史峰值在线：${intNum(it.peak_ccu)} 人<br/>好评率：${pct(it.positive_rate)}（${intNum(it.review_cnt)} 条评论）`
      },
    },
    xAxis: { type: 'value', show: false, max: 'dataMax' },
    yAxis: {
      type: 'category',
      inverse: true,
      data: d.map((x) => x.name),
      axisLabel: { color: color.text, fontSize: 12, width: 170, overflow: 'truncate' },
      animationDuration: 300,
      animationDurationUpdate: 300,
    },
    series: [
      {
        type: 'bar',
        realtimeSort: true,
        data: d.map((x, i) => ({
          value: val(x),
          itemStyle: { color: i < 3 ? color.accent : 'rgba(102,192,244,0.55)', borderRadius: [0, 3, 3, 0] },
        })),
        barMaxWidth: 18,
        label: {
          show: true,
          position: 'right',
          color: color.text,
          fontSize: 12,
          formatter: (p: any) => bigNum(p.value),
        },
        cursor: 'pointer',
      },
    ],
    animationDuration: 600,
    animationDurationUpdate: 800,
    animationEasing: 'linear',
    animationEasingUpdate: 'cubicInOut',
  }
})

function onClick(p: { dataIndex?: number }) {
  const it = r.data.value?.[p.dataIndex ?? -1]
  if (it) router.push(`/game/${it.appid}`)
}
</script>

<template>
  <Panel title="热销 Top10" :note="NOTE[metric]">
    <template #actions>
      <button class="seg" :class="{ on: metric === 'owners' }" @click="metric = 'owners'">拥有者</button>
      <button class="seg" :class="{ on: metric === 'ccu' }" @click="metric = 'ccu'">在线人数</button>
    </template>
    <BaseChart
      :option="option"
      :state="r.state.value"
      :error="r.error.value"
      :empty="!!r.data.value && r.data.value.length === 0"
      :empty-text="metric === 'ccu' ? '还没有在线人数快照' : '当前筛选下没有游戏'"
      :not-merge="false"
      @retry="r.reload"
      @chart-click="onClick"
    />
  </Panel>
</template>

<style scoped>
.seg {
  background: transparent;
  border: 1px solid var(--bg-raised);
  color: var(--text-secondary);
  font-size: 12px;
  padding: 1px 10px;
  border-radius: 3px;
  cursor: pointer;
}
.seg.on {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-dim);
}
</style>
