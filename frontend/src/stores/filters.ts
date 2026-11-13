import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import type { FilterParams, PriceBucket } from '@/api/types'

/**
 * 全局筛选（年份 / 类型 / 价格区间）。
 * 所有可筛选图表 watch `params`，变化即重新请求；树图点击类型时调用 toggleGenre 实现联动。
 */
export const useFiltersStore = defineStore('filters', () => {
  const yearStart = ref<number | null>(null)
  const yearEnd = ref<number | null>(null)
  const genre = ref<string | null>(null)
  const priceBuckets = ref<PriceBucket[]>([])

  /** 转成接口查询参数；没设的不传，后端按"全部"处理 */
  const params = computed<FilterParams>(() => {
    const p: FilterParams = {}
    if (yearStart.value !== null) p.year_start = yearStart.value
    if (yearEnd.value !== null) p.year_end = yearEnd.value
    if (genre.value) p.genre = genre.value
    if (priceBuckets.value.length) p.price_bucket = priceBuckets.value.join(',')
    return p
  })

  const active = computed(() => Object.keys(params.value).length > 0)

  function toggleGenre(g: string) {
    genre.value = genre.value === g ? null : g
  }

  function togglePriceBucket(b: PriceBucket) {
    const set = new Set(priceBuckets.value)
    if (set.has(b)) set.delete(b)
    else set.add(b)
    priceBuckets.value = [...set]
  }

  function setYears(start: number | null, end: number | null) {
    if (start !== null && end !== null && start > end) [start, end] = [end, start]
    yearStart.value = start
    yearEnd.value = end
  }

  function reset() {
    yearStart.value = null
    yearEnd.value = null
    genre.value = null
    priceBuckets.value = []
  }

  return { yearStart, yearEnd, genre, priceBuckets, params, active, toggleGenre, togglePriceBucket, setYears, reset }
})
