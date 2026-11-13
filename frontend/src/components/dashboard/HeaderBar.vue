<script setup lang="ts">
/**
 * 顶栏两行：
 * 1. 标题 · 标签页导航 · 自动轮播开关 · 数据更新时间
 * 2. 全局筛选条（年份 / 类型 / 价格区间多选），切换标签页时保持不变
 */
import { storeToRefs } from 'pinia'
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import { metaApi } from '@/api'
import type { PriceBucket } from '@/api/types'
import { useRemote } from '@/composables/useRemote'
import { useFiltersStore } from '@/stores/filters'
import { dateTime, intNum } from '@/theme/format'
import { CAROUSEL_SECONDS, TABS } from '@/views/tabs/registry'

const autoplay = defineModel<boolean>('autoplay', { required: true })
const emit = defineEmits<{ (e: 'manual-nav'): void }>()

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
  genre.value = (e.target as HTMLSelectElement).value || null
}

const isOn = (k: PriceBucket) => priceBuckets.value.includes(k)
</script>

<template>
  <header class="header">
    <div class="row top">
      <div class="brand">
        <span class="logo" aria-hidden="true" />
        <div>
          <h1>Steam 玩家生态与热销趋势</h1>
          <span class="sub">市场在变 · 玩家在想什么 · 什么游戏会火</span>
        </div>
      </div>

      <nav class="tabs">
        <RouterLink
          v-for="(t, i) in TABS"
          :key="t.name"
          :to="t.path"
          class="tab"
          active-class="on"
          @click="emit('manual-nav')"
        >
          <span class="idx">0{{ i + 1 }}</span>
          <span class="label">{{ t.label }}</span>
          <span class="hint">{{ t.hint }}</span>
        </RouterLink>
      </nav>

      <div class="right">
        <button class="carousel" :class="{ on: autoplay }" :title="`每页停留 ${CAROUSEL_SECONDS} 秒；键盘 ← → 或 1–4 也可切换`" @click="autoplay = !autoplay">
          <span class="dot" />{{ autoplay ? '轮播中' : '自动轮播' }}
        </button>
        <div class="updated">
          <div>数据更新 {{ dateTime(updated.data.value?.data_updated_at, true) }}</div>
          <div>在线快照 {{ dateTime(updated.data.value?.ccu_updated_at) }}</div>
        </div>
      </div>
    </div>

    <div class="row filters">
      <span class="filters-title">全局筛选</span>
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

      <button class="reset" :disabled="!active" @click="filters.reset()">重置筛选</button>
      <span v-if="meta.state.value === 'error'" class="warn">筛选项加载失败：{{ meta.error.value }}（自动重试中）</span>
    </div>
  </header>
</template>

<style scoped>
.header {
  padding: 0 32px;
}
.row {
  display: flex;
  align-items: center;
}
.top {
  height: 88px;
  gap: 32px;
}
.brand {
  display: flex;
  align-items: center;
  gap: 14px;
  width: 520px;
}
.logo {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: radial-gradient(circle at 35% 35%, #d6f0ff, var(--accent) 45%, #1d4f6e 80%);
  box-shadow: 0 0 22px var(--accent-glow);
}
.brand h1 {
  margin: 0;
  font-size: 30px;
  letter-spacing: 2px;
  color: var(--text-strong);
}
.brand .sub {
  font-size: var(--fs-small);
  color: var(--text-secondary);
  letter-spacing: 1px;
}

.tabs {
  flex: 1;
  display: flex;
  justify-content: center;
  gap: 8px;
  padding: 6px;
  border-radius: 18px;
  background: rgba(20, 34, 46, 0.55);
  border: 1px solid var(--glass-border);
  backdrop-filter: blur(12px);
}
.tab {
  display: grid;
  grid-template-columns: auto 1fr;
  grid-template-rows: auto auto;
  column-gap: 10px;
  align-items: center;
  padding: 8px 22px;
  min-width: 190px;
  border-radius: 13px;
  color: var(--text-secondary);
  text-decoration: none;
  transition:
    background 0.25s,
    color 0.25s;
}
.tab:hover {
  background: rgba(102, 192, 244, 0.08);
}
.tab .idx {
  grid-row: span 2;
  font-family: var(--font-number);
  font-size: 22px;
  opacity: 0.6;
}
.tab .label {
  font-size: 19px;
  font-weight: 600;
}
.tab .hint {
  font-size: 13px;
  opacity: 0.8;
}
.tab.on {
  color: var(--text-strong);
  background: linear-gradient(135deg, rgba(102, 192, 244, 0.35), rgba(102, 192, 244, 0.1));
  box-shadow:
    inset 0 0 0 1px rgba(102, 192, 244, 0.55),
    0 0 24px rgba(102, 192, 244, 0.25);
}
.tab.on .idx {
  color: var(--accent);
  opacity: 1;
}

.right {
  display: flex;
  align-items: center;
  gap: 20px;
}
.carousel {
  display: flex;
  align-items: center;
  gap: 8px;
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--glass-border);
  border-radius: 20px;
  padding: 6px 16px;
  font-size: var(--fs-small);
  cursor: pointer;
}
.carousel .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-secondary);
}
.carousel.on {
  color: var(--positive);
  border-color: var(--positive);
}
.carousel.on .dot {
  background: var(--positive);
  box-shadow: 0 0 8px var(--positive);
  animation: pulse 1.4s ease-in-out infinite;
}
@keyframes pulse {
  50% {
    opacity: 0.3;
  }
}
.updated {
  text-align: right;
  font-size: var(--fs-small);
  color: var(--text-secondary);
  line-height: 1.6;
  white-space: nowrap;
}

.filters {
  height: 64px;
  gap: 28px;
  padding: 0 22px;
  border-radius: var(--radius);
  background: rgba(20, 34, 46, 0.5);
  border: 1px solid var(--glass-border);
  backdrop-filter: blur(12px);
}
.filters-title {
  font-size: var(--fs-small);
  color: var(--accent);
  letter-spacing: 2px;
}
.field {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--fs-body);
}
.field > span {
  color: var(--text-secondary);
}
.field em {
  font-style: normal;
  color: var(--text-secondary);
}
select {
  background: rgba(11, 18, 24, 0.8);
  color: var(--text-primary);
  border: 1px solid var(--bg-raised);
  border-radius: 8px;
  padding: 6px 10px;
  font-size: var(--fs-body);
}
select.genre {
  width: 240px;
}
.chip {
  background: transparent;
  color: var(--text-primary);
  border: 1px solid var(--bg-raised);
  border-radius: 16px;
  padding: 5px 14px;
  font-size: var(--fs-small);
  cursor: pointer;
}
.chip.on {
  background: var(--accent-dim);
  border-color: var(--accent);
  color: var(--accent);
}
.reset {
  margin-left: auto;
  background: transparent;
  border: 1px solid var(--accent);
  color: var(--accent);
  border-radius: 8px;
  padding: 6px 18px;
  font-size: var(--fs-small);
  cursor: pointer;
}
.reset:disabled {
  opacity: 0.35;
  cursor: default;
}
.warn {
  color: var(--negative);
  font-size: var(--fs-small);
}
</style>
