<script setup lang="ts">
/** 4 个 KPI 卡：数字从旧值滚动到新值（翻牌效果）；还没有的指标显示"—"并注明原因 */
import { computed, onBeforeUnmount, ref, watch } from 'vue'

import { overviewApi } from '@/api'
import type { Kpi } from '@/api/types'
import { useRemote } from '@/composables/useRemote'
import { bigNum, dateTime, intNum } from '@/theme/format'

const kpi = useRemote((s) => overviewApi.kpi(s), [], { pollMs: 5 * 60_000 })
const k = computed<Kpi | null>(() => {
  const d = kpi.data.value
  return d && 'game_cnt' in d ? (d as Kpi) : null
})

interface Card {
  key: keyof Kpi
  label: string
  unit: string
  fmt: (v: number) => string
  note: (k: Kpi) => string
}

const cards: Card[] = [
  { key: 'game_cnt', label: '游戏总数', unit: '款', fmt: intNum, note: () => '有发行年份的 Steam 游戏' },
  { key: 'review_cnt', label: '评论总数', unit: '条', fmt: bigNum, note: () => '评论元数据全量入库' },
  {
    key: 'owners_total',
    label: '估算玩家总量',
    unit: '份',
    fmt: bigNum,
    note: () => 'SteamSpy 区间中值之和，同一玩家多款重复计',
  },
  {
    key: 'online_peak_24h',
    label: '实时在线峰值',
    unit: '人',
    fmt: intNum,
    note: (k) => (k.online_peak_at ? `近 24 小时，峰值于 ${dateTime(k.online_peak_at)}` : '近 24 小时，采集名单内游戏合计'),
  },
]

// 数字滚动：每张卡独立插值
const shown = ref<Record<string, number | null>>({})
let raf = 0
watch(
  k,
  (val) => {
    cancelAnimationFrame(raf)
    if (!val) return
    const from = { ...shown.value }
    const t0 = performance.now()
    const step = (t: number) => {
      const p = Math.min(1, (t - t0) / 1200)
      const ease = 1 - Math.pow(1 - p, 3)
      const next: Record<string, number | null> = {}
      for (const c of cards) {
        const to = val[c.key] as number | null
        const f = (from[c.key] as number | null) ?? 0
        next[c.key] = to === null ? null : f + (to - f) * ease
      }
      shown.value = next
      if (p < 1) raf = requestAnimationFrame(step)
    }
    raf = requestAnimationFrame(step)
  },
  { immediate: true },
)
onBeforeUnmount(() => cancelAnimationFrame(raf))

function display(c: Card): string {
  const v = shown.value[c.key]
  if (v === null || v === undefined) return '—'
  return c.fmt(Math.round(v))
}
</script>

<template>
  <div class="kpis">
    <div v-for="c in cards" :key="c.key" class="card">
      <div class="label">{{ c.label }}</div>
      <div class="value">
        <span class="num">{{ k ? display(c) :kpi.state.value === 'loading' ? '…' : '—' }}</span>
        <span class="unit">{{ c.unit }}</span>
      </div>
      <div class="note">
        <template v-if="kpi.state.value === 'error' && !k">KPI 加载失败：{{ kpi.error.value }}</template>
        <template v-else-if="k && k[c.key] === null">尚未生成（{{ c.key === 'review_cnt' ? '评论侧聚合未运行' : '在线快照聚合未运行' }}）</template>
        <template v-else-if="k">{{ c.note(k) }}</template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.kpis {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--gap);
  height: 100%;
}
.card {
  position: relative;
  background: linear-gradient(135deg, rgba(102, 192, 244, 0.14), rgba(27, 40, 56, 0.85) 60%);
  border: 1px solid rgba(102, 192, 244, 0.22);
  border-radius: var(--radius);
  padding: 10px 18px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  overflow: hidden;
}
.card::after {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--accent);
}
.label {
  font-size: 14px;
  color: var(--text-secondary);
}
.value {
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.num {
  font-family: var(--font-number);
  font-size: 38px;
  font-weight: 700;
  color: var(--text-strong);
  letter-spacing: 1px;
  text-shadow: 0 0 10px rgba(102, 192, 244, 0.35);
}
.unit {
  font-size: 14px;
  color: var(--accent);
}
.note {
  font-size: 11px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
