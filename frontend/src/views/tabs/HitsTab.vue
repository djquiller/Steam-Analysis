<script setup lang="ts">
/** 04 什么游戏会火：热销 Top10（可切口径）+ 游戏聚类分群；两张图都能点进详情页 */
import ClusterScatter from '@/components/charts/ClusterScatter.vue'
import TopSellersBar from '@/components/charts/TopSellersBar.vue'

defineOptions({ name: 'HitsTab' })
</script>

<template>
  <div class="tab-hits">
    <TopSellersBar />
    <ClusterScatter />
  </div>
</template>

<style scoped>
.tab-hits {
  display: grid;
  grid-template-columns: 1.15fr 1fr;
  gap: var(--gap);
  height: 100%;
}
</style>
