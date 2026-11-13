<script setup lang="ts">
/**
 * 类型热度矩形树图：面积 = 游戏数，颜色深浅 = 好评率。
 * 联动：点击某个类型写入全局筛选 genre，其他图表随之过滤；再点一次取消。
 * 本图不响应 genre（始终展示全部类型），选中的类型高亮。
 */
import { storeToRefs } from 'pinia'
import { computed } from 'vue'

import { trendApi } from '@/api'
import type { ChartOption } from '@/charts/echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import Panel from '@/components/layout/Panel.vue'
import { useRemote } from '@/composables/useRemote'
import { useFiltersStore } from '@/stores/filters'
import { bigNum, intNum, pct } from '@/theme/format'
import { color } from '@/theme/steam-dark'

const store = useFiltersStore()
const { params, genre } = storeToRefs(store)
// genre 变化不需要重新请求本图（后端也不响应），只依赖年份与价格
const deps = computed(() => ({ ...params.value, genre: undefined }))
const r = useRemote((s) => trendApi.genres(deps.value, s), [deps])

const option = computed<ChartOption | null>(() => {
  const d = r.data.value
  if (!d) return null
  const rates = d.map((x) => x.positive_rate ?? 0)
  return {
    tooltip: {
      formatter: (p: any) => {
        const it = d.find((x) => x.genre === p.name)
        if (!it) return p.name
        return `<b>${it.genre}</b><br/>游戏数：${intNum(it.game_cnt)} 款<br/>拥有者合计：${bigNum(it.owners_sum)} 份<br/>好评占比：${pct(it.positive_rate)}（${bigNum(it.review_cnt)} 条评论）<br/><span style="color:${color.accent}">点击${genre.value === it.genre ? '取消' : '按此类型'}筛选</span>`
      },
    },
    visualMap: {
      show: false,
      min: Math.min(...rates),
      max: Math.max(...rates),
      dimension: 1,
      inRange: { color: ['#2a475e', '#3d6f91', '#66c0f4'] },
    },
    series: [
      {
        type: 'treemap',
        roam: false,
        nodeClick: false,
        breadcrumb: { show: false },
        width: '100%',
        height: '100%',
        top: 4,
        label: { show: true, formatter: '{b}', fontSize: 12, color: '#fff' },
        upperLabel: { show: false },
        itemStyle: { borderColor: color.bgPanel, borderWidth: 2, gapWidth: 2 },
        data: d.map((x) => ({
          name: x.genre,
          value: [x.game_cnt, x.positive_rate ?? 0],
          itemStyle:
            genre.value === x.genre
              ? { borderColor: color.warning, borderWidth: 3 }
              : genre.value
                ? { opacity: 0.45 }
                : {},
        })),
      },
    ],
  }
})

function onClick(p: { name?: string }) {
  if (p.name) store.toggleGenre(p.name)
}
</script>

<template>
  <Panel title="类型热度" note="面积：游戏数（款，多类型各计一次）· 颜色：好评占比 · 点击联动筛选">
    <template #actions>
      <span v-if="genre" class="tag" @click="store.toggleGenre(genre)">{{ genre }} ✕</span>
    </template>
    <BaseChart
      :option="option"
      :state="r.state.value"
      :error="r.error.value"
      :empty="!!r.data.value && r.data.value.length === 0"
      @retry="r.reload"
      @chart-click="onClick"
    />
  </Panel>
</template>

<style scoped>
.tag {
  font-size: 11px;
  color: var(--warning);
  border: 1px solid var(--warning);
  border-radius: 10px;
  padding: 0 8px;
  cursor: pointer;
}
</style>
