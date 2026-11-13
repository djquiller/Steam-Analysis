<script setup lang="ts">
/**
 * 全局筛选（年份 / 类型 / 价格区间），以一排紧凑胶囊放在页标题右侧；切换标签页时保持不变。
 * - 发行年份、价格：点胶囊弹出磨砂面板（PillPopover）在里面选；
 * - 类型：胶囊本身就是下拉框，选项多，直接用原生下拉最快；
 * - 有筛选值的胶囊会高亮，价格胶囊带已选档位数的角标。
 */
import { storeToRefs } from 'pinia'
import { computed } from 'vue'

import { metaApi } from '@/api'
import type { PriceBucket } from '@/api/types'
import PillPopover from '@/components/layout/PillPopover.vue'
import { useRemote } from '@/composables/useRemote'
import { useFiltersStore } from '@/stores/filters'
import { intNum } from '@/theme/format'
import { priceBucketMeta } from '@/theme/steam-dark'

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

const yearText = computed(() =>
  yearStart.value === null && yearEnd.value === null
    ? '不限'
    : `${yearStart.value ?? '不限'} — ${yearEnd.value ?? '不限'}`,
)
const priceText = computed(() =>
  priceBuckets.value.length ? priceBuckets.value.map((k) => priceBucketMeta[k].label).join('、') : '不限',
)

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
    <span v-if="meta.state.value === 'error'" class="warn">筛选项加载失败：{{ meta.error.value }}（自动重试中）</span>

    <PillPopover label="发行年份" :value="yearText" :active="yearStart !== null || yearEnd !== null">
      <div class="years">
        <select :value="yearStart ?? ''" @change="onYear('start', $event)">
          <option value="">不限</option>
          <option v-for="y in years" :key="y" :value="y">{{ y }}</option>
        </select>
        <em>—</em>
        <select :value="yearEnd ?? ''" @change="onYear('end', $event)">
          <option value="">不限</option>
          <option v-for="y in years" :key="y" :value="y">{{ y }}</option>
        </select>
      </div>
    </PillPopover>

    <label class="pill genre" :class="{ active: !!genre }">
      <span class="label">类型</span>
      <select :value="genre ?? ''" @change="onGenre">
        <option value="">全部类型</option>
        <option v-for="g in meta.data.value?.genres ?? []" :key="g.genre" :value="g.genre">
          {{ g.genre }}（{{ intNum(g.game_cnt) }}）
        </option>
      </select>
    </label>

    <PillPopover label="价格" :value="priceText" :badge="priceBuckets.length" :active="priceBuckets.length > 0">
      <div class="chips">
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
    </PillPopover>

    <button class="reset" :disabled="!active" @click="filters.reset()">重置筛选</button>
  </div>
</template>

<style scoped>
.filters {
  display: flex;
  align-items: center;
  gap: 12px;
}

/* 类型胶囊：外观与 PillPopover 的胶囊一致，里面是透明的原生下拉框 */
.pill {
  display: flex;
  align-items: center;
  gap: 10px;
  height: 46px;
  padding: 0 8px 0 18px;
  border-radius: 23px;
  color: var(--text-secondary);
  font-size: var(--fs-body);
  white-space: nowrap;
  cursor: pointer;
  background: linear-gradient(110deg, rgba(255, 255, 255, 0.06), rgba(255, 255, 255, 0.015));
  border: 1px solid rgba(255, 255, 255, 0.08);
  backdrop-filter: blur(16px);
  transition:
    border-color 0.35s var(--ease-out),
    background 0.35s var(--ease-out);
}
.pill:hover {
  border-color: rgba(212, 214, 255, 0.35);
}
.pill.active {
  border-color: rgba(212, 214, 255, 0.45);
  background: linear-gradient(110deg, rgba(163, 167, 240, 0.26), rgba(163, 167, 240, 0.06));
}
.genre select {
  width: 190px;
  border: 0;
  background-color: transparent;
  text-overflow: ellipsis;
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
.genre select:hover,
.genre select:focus {
  border-color: transparent;
}
select option {
  background: var(--bg-panel-solid);
}

/* 年份面板 */
.years {
  display: flex;
  align-items: center;
  gap: 10px;
}
.years select {
  width: 120px;
}
.years em {
  font-style: normal;
  color: var(--text-secondary);
}

/* 价格面板：五个档位竖排，选中时背景从中心铺开，按下有回弹 */
.chips {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 170px;
}
.chip {
  position: relative;
  isolation: isolate; /* 让 ::before 的 z-index: -1 落在按钮自己的背景层 */
  overflow: hidden;
  text-align: left;
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 14px;
  padding: 9px 16px;
  font-size: var(--fs-body);
  cursor: pointer;
  transition:
    color 0.35s var(--ease-out),
    border-color 0.35s var(--ease-out),
    transform 0.35s var(--ease-spring);
}
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
  transform: scale(0.96);
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
  height: 46px;
  padding: 0 20px;
  border-radius: 23px;
  color: var(--text-primary);
  background: linear-gradient(110deg, rgba(163, 167, 240, 0.3), rgba(163, 167, 240, 0.1));
  border: 1px solid rgba(212, 214, 255, 0.3);
  font-size: var(--fs-small);
  cursor: pointer;
  white-space: nowrap;
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
