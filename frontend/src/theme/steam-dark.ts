/**
 * ECharts 的 Steam 深色主题与公共颜色。
 * 组件里只引用这里导出的颜色，不写死色值（frontend/CLAUDE.md "图表规范"）。
 */
import * as echarts from 'echarts/core'

import type { PriceBucket } from '@/api/types'

import { FONT_FAMILY } from './fonts'

export const color = {
  bgBase: '#0b1218',
  /** 玻璃卡片背后的近似实色：树图、热力图格子的描边用它，看起来像卡片上的缝 */
  bgPanel: '#122230',
  bgRaised: '#2a475e',
  accent: '#66c0f4',
  text: '#d3dee7',
  textSecondary: '#8fa3b3',
  textStrong: '#ffffff',
  positive: '#a4d007',
  negative: '#c35c2c',
  warning: '#e8a33d',
  magenta: '#e05ea8',
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

/** 图表字号（设计稿像素）。大屏在 3–5 米外看，坐标轴、标签都不小于 14 */
export const font = {
  small: 14,
  label: 15,
  axis: 14,
  strong: 18,
} as const

export const THEME_NAME = 'steam-dark'

const axisCommon = {
  axisLine: { lineStyle: { color: color.bgRaised } },
  axisTick: { show: false },
  axisLabel: { color: color.textSecondary, fontSize: font.axis },
  splitLine: { lineStyle: { color: color.grid } },
  nameTextStyle: { color: color.textSecondary, fontSize: font.axis },
}

echarts.registerTheme(THEME_NAME, {
  color: palette,
  backgroundColor: 'transparent',
  textStyle: { fontFamily: FONT_FAMILY, color: color.text },
  title: { textStyle: { color: color.text } },
  legend: { textStyle: { color: color.text, fontSize: font.label }, itemWidth: 16, itemHeight: 10, itemGap: 16 },
  tooltip: {
    backgroundColor: 'rgba(11, 18, 24, 0.92)',
    borderColor: 'rgba(102, 192, 244, 0.35)',
    borderRadius: 10,
    padding: [10, 14],
    textStyle: { color: color.text, fontSize: font.label },
    extraCssText: `font-family: ${FONT_FAMILY}; backdrop-filter: blur(8px); box-shadow: 0 8px 24px rgba(0,0,0,0.45);`,
  },
  categoryAxis: { ...axisCommon, splitLine: { show: false } },
  valueAxis: axisCommon,
  timeAxis: axisCommon,
  visualMap: { textStyle: { color: color.textSecondary } },
})
