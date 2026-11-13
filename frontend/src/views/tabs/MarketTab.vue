<script setup lang="ts">
/** 02 市场在变：类型热度（点击联动全局筛选）+ 价格区间 × 好评率 */
import GenreTreemap from '@/components/charts/GenreTreemap.vue'
import PriceRatingBox from '@/components/charts/PriceRatingBox.vue'

defineOptions({ name: 'MarketTab' })
</script>

<template>
  <div class="tab-market">
    <GenreTreemap />
    <PriceRatingBox />
  </div>
</template>

<style scoped>
.tab-market {
  display: grid;
  grid-template-columns: 1.3fr 1fr;
  gap: var(--gap);
  height: 100%;
}
</style>
