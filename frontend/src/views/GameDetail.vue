<script setup lang="ts">
/**
 * 单款游戏详情（从 Top10 / 聚类散点 / 在线榜下钻进来）：
 * 基本信息、聚类标签、热销预测、情感占比、评论月度走势、价格历史、同类对比。
 * 模型结果表里没有这款游戏时对应区块显示"尚未生成"，不填假数据。
 */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { gamesApi } from '@/api'
import type { ChartOption } from '@/charts/echarts'
import BaseChart from '@/components/charts/BaseChart.vue'
import Panel from '@/components/layout/Panel.vue'
import ScreenContainer from '@/components/layout/ScreenContainer.vue'
import { useRemote } from '@/composables/useRemote'
import { bigNum, hours, intNum, pct, usd } from '@/theme/format'
import { barGradient, color, hbarGradient, priceBucketMeta } from '@/theme/steam-dark'

const route = useRoute()
const router = useRouter()
const appid = computed(() => Number(route.params.appid))

const detail = useRemote((s) => gamesApi.detail(appid.value, s), [appid])
const trend = useRemote((s) => gamesApi.reviewsTrend(appid.value, s), [appid])
const prices = useRemote((s) => gamesApi.priceHistory(appid.value, s), [appid])
const g = computed(() => detail.data.value)

function back() {
  if (window.history.length > 1) router.back()
  else router.push('/')
}

const facts = computed(() => {
  const x = g.value
  if (!x) return []
  return [
    { label: '拥有者', value: x.owners_mid === null ? '—' : `${bigNum(x.owners_low)}–${bigNum(x.owners_high)}`, unit: '份（SteamSpy 区间）' },
    { label: '历史峰值在线', value: intNum(x.peak_ccu), unit: '人' },
    { label: '评论数', value: bigNum(x.review_cnt), unit: '条（Steam 官方好评 + 差评）' },
    { label: '好评率', value: pct(x.positive_rate), unit: x.review_cnt < 10 ? '评论少于 10 条，不计' : '' },
    { label: '平均游玩', value: hours(x.avg_playtime_min), unit: `中位 ${hours(x.median_playtime_min)}` },
    { label: 'Metacritic', value: x.metacritic_score === null ? '—' : String(x.metacritic_score), unit: '分' },
  ]
})

const trendOption = computed<ChartOption | null>(() => {
  const d = trend.data.value
  if (!d) return null
  return {
    grid: { left: 52, right: 48, top: 30, bottom: 30 },
    legend: { top: 0, right: 0, data: ['评论数', '好评占比'] },
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: d.map((x) => x.month) },
    yAxis: [
      { type: 'value', name: '条' },
      { type: 'value', name: '%', min: 0, max: 100, splitLine: { show: false } },
    ],
    series: [
      { name: '评论数', type: 'bar', data: d.map((x) => x.review_cnt), itemStyle: { color: barGradient(), borderRadius: [6, 6, 2, 2] } },
      {
        name: '好评占比',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        symbol: 'none',
        data: d.map((x) => (x.positive_rate === null ? null : +(x.positive_rate * 100).toFixed(1))),
        lineStyle: { color: '#ffffff', width: 2.5, shadowColor: 'rgba(212, 214, 255, 0.8)', shadowBlur: 10 },
        itemStyle: { color: '#ffffff' },
      },
    ],
  }
})

const priceOption = computed<ChartOption | null>(() => {
  const d = prices.data.value
  if (!d) return null
  return {
    grid: { left: 52, right: 20, top: 20, bottom: 30 },
    tooltip: { trigger: 'axis', valueFormatter: (v: number) => usd(v) },
    xAxis: { type: 'category', data: d.map((x) => x.date) },
    yAxis: { type: 'value', name: '美元', min: 0 },
    series: [{ type: 'line', step: 'end', data: d.map((x) => x.price_usd), lineStyle: { color: color.accentBright, width: 2.5 }, itemStyle: { color: color.accentBright }, areaStyle: { color: barGradient(color.accent, 0) } }],
  }
})

const peerOption = computed<ChartOption | null>(() => {
  const x = g.value
  if (!x || !x.peers) return null
  const p = x.peers
  // 各指标量纲不同，按"本游戏 ÷ 同簇平均"画相对倍数，tooltip 给出原值
  const rows = [
    { name: '价格', self: x.price_usd, avg: p.avg_price_usd, fmt: usd },
    { name: '好评率', self: x.positive_rate, avg: p.avg_positive_rate, fmt: (v: number | null) => pct(v) },
    { name: '拥有者', self: x.owners_mid, avg: p.avg_owners_mid, fmt: (v: number | null) => bigNum(v) },
    { name: '平均游玩', self: x.avg_playtime_min, avg: p.avg_playtime_min, fmt: (v: number | null) => hours(v) },
  ]
  return {
    grid: { left: 70, right: 30, top: 10, bottom: 24 },
    tooltip: {
      formatter: (q: any) => {
        const r = rows[q.dataIndex]
        if (!r) return ''
        return `${r.name}<br/>本游戏：${r.fmt(r.self as number)}<br/>同簇平均：${r.fmt(r.avg)}`
      },
    },
    xAxis: { type: 'value', name: '倍', axisLabel: { formatter: '{value}×' } },
    yAxis: { type: 'category', data: rows.map((r) => r.name), inverse: true },
    series: [
      {
        type: 'bar',
        barMaxWidth: 16,
        data: rows.map((r) => (r.self === null || !r.avg ? 0 : +(Number(r.self) / r.avg).toFixed(2))),
        itemStyle: { color: hbarGradient(), borderRadius: [0, 10, 10, 0] },
        markLine: { symbol: 'none', data: [{ xAxis: 1 }], lineStyle: { color: '#ffffff', type: 'dashed' }, label: { formatter: '同簇平均', color: color.text } },
      },
    ],
  }
})
</script>

<template>
  <ScreenContainer>
    <div class="detail">
      <header class="top">
        <button class="back" @click="back">← 返回大屏</button>
        <h1>{{ g?.name ?? (detail.state.value === 'loading' ? '加载中…' : '游戏详情') }}</h1>
        <span class="appid">appid {{ appid }}</span>
      </header>

      <div v-if="detail.state.value === 'error' && !g" class="fatal">
        <p>{{ detail.error.value }}</p>
        <button class="back" @click="detail.reload">重试</button>
      </div>

      <main v-else-if="g" class="grid">
        <section class="info card glass">
          <img v-if="g.header_image" :src="g.header_image" :alt="g.name" class="cover" referrerpolicy="no-referrer" />
          <div class="meta">
            <div><span>发行</span>{{ g.release_date ?? '未发行' }}</div>
            <div><span>价格</span>{{ usd(g.price_usd) }}<em class="bucket" :style="{ color: priceBucketMeta[g.price_bucket]?.color }">{{ priceBucketMeta[g.price_bucket]?.label }}</em></div>
            <div><span>开发 / 发行</span>{{ g.developer ?? '—' }} / {{ g.publisher ?? '—' }}</div>
            <div><span>平台</span>{{ g.platforms.join(' · ') || '—' }}</div>
            <div><span>类型</span><em v-for="x in g.genres" :key="x" class="tag">{{ x }}</em><template v-if="!g.genres.length">—</template></div>
            <div><span>其他</span>{{ intNum(g.dlc_count) }} 个 DLC · {{ intNum(g.achievements) }} 个成就 · 支持 {{ intNum(g.num_languages) }} 种语言 · {{ g.required_age ? `${g.required_age}+` : '无年龄限制' }}</div>
          </div>
        </section>

        <section class="facts">
          <div v-for="f in facts" :key="f.label" class="fact card glass">
            <div class="label">{{ f.label }}</div>
            <div class="value">{{ f.value }}</div>
            <div class="unit">{{ f.unit }}</div>
          </div>
        </section>

        <section class="models">
          <div class="model card glass">
            <div class="label">聚类分群</div>
            <template v-if="g.cluster"><div class="value">{{ g.cluster.cluster_label }}</div><div class="unit">簇 #{{ g.cluster.cluster_id }}</div></template>
            <div v-else class="pending">尚未生成（聚类模型未运行，或评论数不足 10 条）</div>
          </div>
          <div class="model card glass">
            <div class="label">热销预测</div>
            <template v-if="g.hot_pred">
              <div class="value">{{ pct(g.hot_pred.hot_prob) }}<small>{{ g.hot_pred.hot_pred ? ' 预测热销' : ' 预测非热销' }}</small></div>
              <div class="unit">实际：{{ g.hot_pred.hot_actual ? '热销' : '非热销' }} · {{ g.hot_pred.model_name }}{{ g.hot_pred.is_test ? ' · 测试集' : ' · 模型训练时见过这款游戏' }}</div>
            </template>
            <div v-else class="pending">尚未生成（热销预测模型未运行）</div>
          </div>
          <div class="model card glass">
            <div class="label">评论情感</div>
            <template v-if="g.sentiment">
              <div class="value">{{ pct(g.sentiment.positive_ratio) }}<small> 正向</small></div>
              <div class="unit">抽样 {{ g.sentiment.sample_cnt }} 条 · {{ g.sentiment.method === 'model' ? '情感模型打分' : '按玩家推荐统计' }}</div>
            </template>
            <div v-else class="pending">尚未生成（情感模型未运行）</div>
          </div>
        </section>

        <Panel class="p-trend" title="评论月度走势" note="评论数（条）· 好评占比（%）· 月份（UTC）">
          <BaseChart :option="trendOption" :state="trend.state.value" :error="trend.error.value" :empty="!!trend.data.value && !trend.data.value.length" empty-text="评论月度聚合尚未生成" @retry="trend.reload" />
        </Panel>
        <Panel class="p-price" title="价格历史" note="价格（美元）· 每日采集">
          <BaseChart :option="priceOption" :state="prices.state.value" :error="prices.error.value" :empty="!!prices.data.value && !prices.data.value.length" empty-text="价格快照尚未开始采集" @retry="prices.reload" />
        </Panel>
        <Panel class="p-peer" title="同类对比" :note="g.peers ? `与同簇「${g.peers.cluster_label}」${intNum(g.peers.game_cnt)} 款游戏的平均值相比（倍数）` : '与同一聚类的游戏平均值相比'">
          <BaseChart :option="peerOption" state="ready" :empty="!g.peers" empty-text="聚类结果尚未生成，暂无同类对比" />
        </Panel>
      </main>
    </div>
  </ScreenContainer>
</template>

<style scoped>
.detail {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 0 32px 28px;
}
.top {
  height: 88px;
  flex: none;
  display: flex;
  align-items: center;
  gap: 24px;
}
.top h1 {
  margin: 0;
  font-size: 32px;
  letter-spacing: 1px;
  color: var(--text-strong);
}
.appid {
  color: var(--text-secondary);
  font-size: var(--fs-small);
}
.back {
  background: var(--accent-dim);
  border: 1px solid var(--accent);
  color: var(--accent);
  border-radius: 10px;
  padding: 8px 20px;
  font-size: var(--fs-body);
  cursor: pointer;
}
.fatal {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: var(--negative);
  font-size: 20px;
}
.grid {
  flex: 1;
  min-height: 0;
  display: grid;
  gap: var(--gap);
  grid-template-columns: 1fr 1fr 1fr;
  /* 上两行按内容定高（大字号下也放得下），下面两行图表平分剩余高度 */
  grid-template-rows: 300px 150px minmax(0, 1fr) minmax(0, 1fr);
  grid-template-areas:
    'info info facts'
    'models models models'
    'trend trend peer'
    'price price peer';
}
.card {
  min-width: 0;
  min-height: 0;
  padding: 18px 22px;
  animation: card-in 0.8s var(--ease-out) backwards;
}
.card > * {
  position: relative;
  z-index: 2;
}
.facts .card:nth-child(n + 3),
.models .card:nth-child(2) {
  animation-delay: 0.08s;
}
.facts .card:nth-child(n + 5),
.models .card:nth-child(3) {
  animation-delay: 0.16s;
}
.info {
  grid-area: info;
  display: flex;
  gap: 28px;
}
.cover {
  height: 100%;
  aspect-ratio: 460 / 215;
  object-fit: cover;
  border-radius: 10px;
  flex: none;
}
.meta {
  display: flex;
  flex-direction: column;
  justify-content: space-around;
  font-size: 17px;
  min-width: 0;
}
.meta span {
  display: inline-block;
  width: 120px;
  color: var(--text-secondary);
}
.bucket {
  font-style: normal;
  margin-left: 12px;
  font-size: var(--fs-small);
}
.tag {
  font-style: normal;
  font-size: var(--fs-small);
  border: 1px solid var(--bg-raised);
  border-radius: 12px;
  padding: 1px 10px;
  margin-right: 8px;
}
.facts {
  grid-area: facts;
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.fact {
  padding: 10px 18px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.models {
  grid-area: models;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--gap);
}
.model {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
}
.label {
  font-size: var(--fs-small);
  color: var(--text-secondary);
}
.value {
  font-family: var(--font-number);
  font-size: 28px;
  line-height: 1.2;
  color: var(--text-strong);
  font-weight: 700;
}
.model .value {
  font-size: 34px;
}
.value small {
  font-size: 16px;
  color: var(--accent);
  font-weight: 400;
}
.unit {
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.pending {
  margin-top: 8px;
  color: var(--text-secondary);
  font-size: var(--fs-body);
}
.p-trend {
  grid-area: trend;
}
.p-price {
  grid-area: price;
}
.p-peer {
  grid-area: peer;
}
</style>
