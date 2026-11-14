<script setup lang="ts">
/** 01 总览：四个大号 KPI + 历年发行趋势（主视觉）+ 实时在线榜 */
import OnlineLiveList from '@/components/charts/OnlineLiveList.vue'
import YearlyChart from '@/components/charts/YearlyChart.vue'
import KpiCards from '@/components/dashboard/KpiCards.vue'

defineOptions({ name: 'OverviewTab' })
</script>

<template>
  <div class="tab-overview">
    <KpiCards class="kpis" />
    <div class="row">
      <YearlyChart />
      <OnlineLiveList />
    </div>
  </div>
</template>

<style scoped>
.tab-overview {
  display: grid;
  grid-template-rows: 200px 1fr;
  gap: var(--gap);
  height: 100%;
}
.row {
  display: grid;
  grid-template-columns: 1.75fr 1fr;
  gap: var(--gap);
  min-height: 0;
}
</style>
