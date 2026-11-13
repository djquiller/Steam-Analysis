<script setup lang="ts">
/** 顶栏：标题、全局筛选（年份 / 类型 / 价格区间多选）、数据更新时间 */
import { storeToRefs } from 'pinia'
import { computed } from 'vue'

import { metaApi } from '@/api'
import type { PriceBucket } from '@/api/types'
import { useRemote } from '@/composables/useRemote'
import { useFiltersStore } from '@/stores/filters'
import { dateTime, intNum } from '@/theme/format'

const filters = useFiltersStore()
const { yearStart, yearEnd, genre, priceBuckets, active } = storeToRefs(filters)

const meta = useRemote((s) => metaApi.filters(s))
const updated = useRemote((s) => metaApi.updatedAt(s))

const years = computed(() => {
  const y = meta.data.value?.years
  if (!y || y.min === null || y.max === null) return []
  const out: number[] = []
  for (let i = y.max; i >= y.min; i--) out.push(i)
  return out
})

function onYear(which: 'start' | 'end', e: Event) {
  const v = (e.target as HTMLSelectElement).value
  const n = v === '' ? null : Number(v)
  if (which === 'start') filters.setYears(n, yearEnd.value)
  else filters.setYears(yearStart.value, n)
}

function onGenre(e: Event) {
  const v = (e.target as HTMLSelectElement).value
  genre.value = v || null
}

const isOn = (k: PriceBucket) => priceBuckets.value.includes(k)
</script>

<template>
  <header class="header">
    <div class="brand">
      <h1>Steam 玩家生态与热销趋势</h1>
      <span class="sub">市场在变 · 玩家在想什么 · 什么游戏会火</span>
    </div>

    <div class="filters">
      <label class="field">
        <span>发行年份</span>
        <select :value="yearStart ?? ''" @change="onYear('start', $event)">
          <option value="">不限</option>
          <option v-for="y in years" :key="y" :value="y">{{ y }}</option>
        </select>
        <em>—</em>
        <select :value="yearEnd ?? ''" @change="onYear('end', $event)">
          <option value="">不限</option>
          <option v-for="y in years" :key="y" :value="y">{{ y }}</option>
        </select>
      </label>

      <label class="field">
        <span>类型</span>
        <select class="genre" :value="genre ?? ''" @change="onGenre">
          <option value="">全部类型</option>
          <option v-for="g in meta.data.value?.genres ?? []" :key="g.genre" :value="g.genre">
            {{ g.genre }}（{{ intNum(g.game_cnt) }}）
          </option>
        </select>
      </label>

      <div class="field">
        <span>价格</span>
        <button
          v-for="b in meta.data.value?.price_buckets ?? []"
          :key="b.key"
          class="chip"
          :class="{ on: isOn(b.key) }"
          :title="`${intNum(b.game_cnt)} 款`"
          @click="filters.togglePriceBucket(b.key)"
        >
          {{ b.label }}
        </button>
      </div>

      <button class="reset" :disabled="!active" @click="filters.reset()">重置</button>
      <span v-if="meta.state.value === 'error'" class="warn">筛选项加载失败：{{ meta.error.value }}</span>
    </div>

    <div class="updated">
      <div>数据更新 {{ dateTime(updated.data.value?.data_updated_at, true) }}</div>
      <div>在线人数 {{ dateTime(updated.data.value?.ccu_updated_at) }}</div>
    </div>
  </header>
</template>

<style scoped>
.header {
  height: 72px;
  display: flex;
  align-items: center;
  gap: 28px;
  padding: 0 24px;
  border-bottom: 1px solid rgba(102, 192, 244, 0.18);
  background: linear-gradient(180deg, rgba(42, 71, 94, 0.55), rgba(23, 26, 33, 0));
}
.brand h1 {
  margin: 0;
  font-size: 26px;
  letter-spacing: 2px;
  color: var(--text-strong);
  text-shadow: 0 0 12px rgba(102, 192, 244, 0.45);
}
.brand .sub {
  font-size: 12px;
  color: var(--accent);
  letter-spacing: 3px;
}
.filters {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 22px;
}
.field {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}
.field > span {
  color: var(--text-secondary);
}
.field em {
  font-style: normal;
  color: var(--text-secondary);
}
select {
  background: var(--bg-panel);
  color: var(--text-primary);
  border: 1px solid var(--bg-raised);
  border-radius: 4px;
  padding: 4px 6px;
  font-size: 13px;
}
select.genre {
  width: 190px;
}
.chip {
  background: transparent;
  color: var(--text-primary);
  border: 1px solid var(--bg-raised);
  border-radius: 12px;
  padding: 3px 11px;
  font-size: 12px;
  cursor: pointer;
}
.chip.on {
  background: var(--accent-dim);
  border-color: var(--accent);
  color: var(--accent);
}
.reset {
  background: transparent;
  border: 1px solid var(--accent);
  color: var(--accent);
  border-radius: 4px;
  padding: 4px 14px;
  cursor: pointer;
}
.reset:disabled {
  opacity: 0.35;
  cursor: default;
}
.warn {
  color: var(--negative);
  font-size: 12px;
}
.updated {
  text-align: right;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
  white-space: nowrap;
}
</style>
