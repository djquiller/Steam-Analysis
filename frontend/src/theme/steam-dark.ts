/**
 * ECharts 的 Steam 深色主题与公共颜色。
 * 组件里只引用这里导出的颜色，不写死色值（frontend/CLAUDE.md "图表规范"）。
 */
import * as echarts from 'echarts/core'

import type { PriceBucket } from '@/api/types'

export const color = {
  bgBase: '#171a21',
  bgPanel: '#1b2838',
  bgRaised: '#2a475e',
  accent: '#66c0f4',
  text: '#c7d5e0',
  textSecondary: '#8f98a0',
  textStrong: '#ffffff',
  positive: '#a4d007',
  negative: '#c35c2c',
  warning: '#e8a33d',
  grid: 'rgba(199, 213, 224, 0.08)',
} as const

/** 分类色板：第一个是主强调色；聚类等多系列按顺序取 */
export const palette = [
  '#66c0f4',
  '#a4d007',
  '#e8a33d',
  '#b48ae0',
  '#4fc3a1',
  '#c35c2c',
  '#f06d9a',
  '#8ba3b8',
]

/** 价格区间的固定配色与中文名，各图保持一致 */
export const priceBucketMeta: Record<PriceBucket, { label: string; color: string }> = {
  free: { label: '免费', color: '#4fc3a1' },
  lt10: { label: '$10 以下', color: '#66c0f4' },
  '10_30': { label: '$10–30', color: '#a4d007' },
  '30_60': { label: '$30–60', color: '#e8a33d' },
  ge60: { label: '$60 及以上', color: '#c35c2c' },
}

export const THEME_NAME = 'steam-dark'

const axisCommon = {
  axisLine: { lineStyle: { color: color.bgRaised } },
  axisTick: { show: false },
  axisLabel: { color: color.textSecondary, fontSize: 11 },
  splitLine: { lineStyle: { color: color.grid } },
  nameTextStyle: { color: color.textSecondary, fontSize: 11 },
}

echarts.registerTheme(THEME_NAME, {
  color: palette,
  backgroundColor: 'transparent',
  textStyle: { fontFamily: "'Microsoft YaHei', 'PingFang SC', system-ui, sans-serif", color: color.text },
  title: { textStyle: { color: color.text } },
  legend: { textStyle: { color: color.text, fontSize: 11 }, itemWidth: 12, itemHeight: 8 },
  tooltip: {
    backgroundColor: 'rgba(23, 26, 33, 0.95)',
    borderColor: color.bgRaised,
    textStyle: { color: color.text, fontSize: 12 },
  },
  categoryAxis: { ...axisCommon, splitLine: { show: false } },
  valueAxis: axisCommon,
  timeAxis: axisCommon,
  visualMap: { textStyle: { color: color.textSecondary } },
})
