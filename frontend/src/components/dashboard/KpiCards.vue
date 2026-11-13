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
    <div v-for="c in cards" :key="c.key" class="card glass">
      <div class="label">{{ c.label }}</div>
      <div class="value">
        <span class="num">{{ k ? display(c) : kpi.state.value === 'loading' ? '…' : '—' }}</span>
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
  padding: 24px 28px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  overflow: hidden;
}
/* 右侧一块淡淡的网格纹理，呼应参考稿 KPI 卡里的小图区域（纯装饰，不放数据） */
.card::after {
  content: '';
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 42%;
  background:
    linear-gradient(rgba(255, 255, 255, 0.045) 1px, transparent 1px) 0 0 / 100% 22px,
    linear-gradient(90deg, rgba(255, 255, 255, 0.045) 1px, transparent 1px) 0 0 / 22px 100%;
  -webkit-mask: linear-gradient(90deg, transparent, #000 60%);
  mask: linear-gradient(90deg, transparent, #000 60%);
  pointer-events: none;
}
.label {
  position: relative;
  font-size: 18px;
  color: var(--text-secondary);
  letter-spacing: 0.5px;
}
.value {
  position: relative;
  display: flex;
  white-space: nowrap;
  align-items: baseline;
  gap: 10px;
}
.num {
  font-family: var(--font-number);
  font-size: var(--fs-kpi);
  font-weight: 400;
  line-height: 1.1;
  letter-spacing: -0.5px;
  color: var(--text-strong);
  text-shadow: 0 0 24px rgba(163, 167, 240, 0.35);
}
.unit {
  font-size: 22px;
  color: var(--accent);
}
.note {
  position: relative;
  font-size: var(--fs-small);
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
