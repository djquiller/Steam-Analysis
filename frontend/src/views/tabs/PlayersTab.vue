<script setup lang="ts">
/** 03 评论与口碑：口碑（好评率、语言）与行为（游玩时长、活跃时段），2 × 2 大卡片 */
import ActivityHeatmap from '@/components/charts/ActivityHeatmap.vue'
import LanguageBar from '@/components/charts/LanguageBar.vue'
import PlaytimeChart from '@/components/charts/PlaytimeChart.vue'
import RatingDistChart from '@/components/charts/RatingDistChart.vue'

defineOptions({ name: 'PlayersTab' })
</script>

<template>
  <div class="tab-players">
    <RatingDistChart />
    <LanguageBar />
    <PlaytimeChart />
    <ActivityHeatmap />
  </div>
</template>

<style scoped>
.tab-players {
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr 1fr;
  gap: var(--gap);
  height: 100%;
}
</style>
