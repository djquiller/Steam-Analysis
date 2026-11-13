<script setup lang="ts">
/**
 * 主屏（1920×1080）：顶部筛选与 KPI，下面三栏讲一条线——
 * 左：市场在变；中：什么游戏会火；右：玩家在想什么。
 */
import ActivityHeatmap from '@/components/charts/ActivityHeatmap.vue'
import ClusterScatter from '@/components/charts/ClusterScatter.vue'
import GenreTreemap from '@/components/charts/GenreTreemap.vue'
import LanguageBar from '@/components/charts/LanguageBar.vue'
import OnlineLiveList from '@/components/charts/OnlineLiveList.vue'
import PlaytimeChart from '@/components/charts/PlaytimeChart.vue'
import PriceRatingBox from '@/components/charts/PriceRatingBox.vue'
import RatingDistChart from '@/components/charts/RatingDistChart.vue'
import TopSellersBar from '@/components/charts/TopSellersBar.vue'
import YearlyChart from '@/components/charts/YearlyChart.vue'
import HeaderBar from '@/components/dashboard/HeaderBar.vue'
import KpiCards from '@/components/dashboard/KpiCards.vue'
import ScreenContainer from '@/components/layout/ScreenContainer.vue'
</script>

<template>
  <ScreenContainer>
    <div class="dashboard">
      <HeaderBar />
      <div class="kpi-row"><KpiCards /></div>
      <main class="columns">
        <section class="col">
          <h2 class="col-title">市场在变</h2>
          <div class="stack three">
            <YearlyChart />
            <GenreTreemap />
            <PriceRatingBox />
          </div>
        </section>
        <section class="col">
          <h2 class="col-title">什么游戏会火</h2>
          <div class="stack center">
            <TopSellersBar />
            <OnlineLiveList />
            <ClusterScatter />
          </div>
        </section>
        <section class="col">
          <h2 class="col-title">玩家在想什么</h2>
          <div class="stack four">
            <RatingDistChart />
            <LanguageBar />
            <PlaytimeChart />
            <ActivityHeatmap />
          </div>
        </section>
      </main>
    </div>
  </ScreenContainer>
</template>

<style scoped>
.dashboard {
  height: 1080px;
  display: grid;
  grid-template-rows: 72px 108px 1fr;
}
.kpi-row {
  padding: 14px 18px 0;
}
.columns {
  display: grid;
  grid-template-columns: 590px 1fr 590px;
  gap: var(--gap);
  padding: 10px 18px 16px;
  min-height: 0;
}
.col {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.col-title {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 400;
  letter-spacing: 6px;
  color: var(--accent);
  text-align: center;
  background: linear-gradient(90deg, transparent, rgba(102, 192, 244, 0.16), transparent);
  line-height: 24px;
}
.stack {
  flex: 1;
  display: grid;
  gap: var(--gap);
  min-height: 0;
}
.stack.three {
  grid-template-rows: 1fr 1.15fr 1fr;
}
.stack.center {
  grid-template-rows: 1.15fr 0.95fr 1.25fr;
}
.stack.four {
  grid-template-rows: repeat(4, 1fr);
}
</style>
