<script setup lang="ts">
/**
 * 全局筛选条（年份 / 类型 / 价格区间多选），放在主区标题下方的一条磨砂胶囊里；切换标签页时保持不变。
 * 价格档位选中时胶囊背景平滑填充，按下有轻微回弹。
 */
import { storeToRefs } from 'pinia'
import { computed } from 'vue'

import { metaApi } from '@/api'
import type { PriceBucket } from '@/api/types'
import { useRemote } from '@/composables/useRemote'
import { useFiltersStore } from '@/stores/filters'
import { intNum } from '@/theme/format'

const filters = useFiltersStore()
const { yearStart, yearEnd, genre, priceBuckets, active } = storeToRefs(filters)

const meta = useRemote((s) => metaApi.filters(s))

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
  <div class="filters">
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
</template>

<style scoped>
.filters {
  display: flex;
  align-items: center;
  gap: 26px;
  height: 60px;
  padding: 0 10px 0 22px;
  border-radius: 30px;
  background: linear-gradient(110deg, rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.015));
  border: 1px solid rgba(255, 255, 255, 0.07);
  backdrop-filter: blur(18px);
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
  appearance: none;
  background:
    linear-gradient(45deg, transparent 50%, var(--text-secondary) 50%) calc(100% - 15px) 52% / 5px 5px no-repeat,
    linear-gradient(-45deg, transparent 50%, var(--text-secondary) 50%) calc(100% - 10px) 52% / 5px 5px no-repeat,
    rgba(255, 255, 255, 0.04);
  color: var(--text-primary);
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 18px;
  padding: 7px 30px 7px 14px;
  font-size: var(--fs-body);
  cursor: pointer;
  transition: border-color 0.35s var(--ease-out);
}
select:hover,
select:focus {
  border-color: rgba(212, 214, 255, 0.35);
  outline: none;
}
select option {
  background: var(--bg-panel-solid);
}
select.genre {
  width: 250px;
}
.chip {
  position: relative;
  isolation: isolate; /* 让 ::before 的 z-index: -1 落在按钮自己的背景层，而不是整条筛选栏后面 */
  overflow: hidden;
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 18px;
  padding: 7px 15px;
  font-size: var(--fs-small);
  cursor: pointer;
  transition:
    color 0.35s var(--ease-out),
    border-color 0.35s var(--ease-out),
    transform 0.35s var(--ease-spring);
}
/* 选中时背景从中心铺开 */
.chip::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: linear-gradient(110deg, rgba(163, 167, 240, 0.4), rgba(163, 167, 240, 0.12));
  transform: scale(0.4);
  opacity: 0;
  transition:
    transform 0.45s var(--ease-out),
    opacity 0.35s var(--ease-out);
  z-index: -1;
}
.chip:hover {
  color: var(--text-primary);
  border-color: rgba(212, 214, 255, 0.3);
}
.chip:active {
  transform: scale(0.94);
}
.chip.on {
  color: var(--text-strong);
  border-color: rgba(212, 214, 255, 0.45);
}
.chip.on::before {
  transform: none;
  opacity: 1;
}
.reset {
  margin-left: auto;
  height: 42px;
  padding: 0 20px;
  border-radius: 21px;
  color: var(--text-primary);
  background: linear-gradient(110deg, rgba(163, 167, 240, 0.3), rgba(163, 167, 240, 0.1));
  border: 1px solid rgba(212, 214, 255, 0.3);
  font-size: var(--fs-small);
  cursor: pointer;
  transition:
    opacity 0.35s var(--ease-out),
    transform 0.35s var(--ease-spring);
}
.reset:active:not(:disabled) {
  transform: scale(0.95);
}
.reset:disabled {
  opacity: 0.3;
  cursor: default;
}
.warn {
  color: var(--negative);
  font-size: var(--fs-small);
}
</style>
