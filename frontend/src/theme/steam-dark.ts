/**
 * ECharts 主题与公共颜色：深靛黑底 + 薰衣草紫单色系（2026-11-13 改版，参考深色分析控制台）。
 * 组件里只引用这里导出的颜色，不写死色值（frontend/CLAUDE.md "图表规范"）。
 * CSS 侧的同一套颜色在 tokens.css，两边改色要一起改。
 */
import * as echarts from 'echarts/core'

import type { PriceBucket } from '@/api/types'

import { FONT_FAMILY } from './fonts'

export const color = {
  bgBase: '#0b0c16',
  /** 磨砂卡片背后的近似实色：树图、热力图格子的描边用它，看起来像卡片上的缝 */
  bgPanel: '#161726',
  bgRaised: '#2c2e4a',
  /** 主强调：薰衣草紫 */
  accent: '#a3a7f0',
  /** 强调的亮端，用于最高值、选中、发光 */
  accentBright: '#d4d6ff',
  /** 强调的暗端 */
  accentDeep: '#5a5ea8',
  text: '#e3e4f2',
  textSecondary: '#8c8ea9',
  textStrong: '#ffffff',
  /** 语义色降低饱和度，融进单色系里，只用于升降、好评差评这类必须区分的地方 */
  positive: '#9ed6b8',
  negative: '#e59aa6',
  warning: '#e3cf9a',
  grid: 'rgba(227, 228, 242, 0.06)',
} as const

/** 分类色板：单色系里拉开明度与色相的 8 个颜色，聚类等多系列按顺序取 */
export const palette = [
  '#a3a7f0',
  '#e8e9f7',
  '#6f74cf',
  '#c9b8f2',
  '#8fb4e8',
  '#565a9c',
  '#d9a8d6',
  '#8c8ea9',
]

/** 顺序色阶（暗 → 亮），树图、热力图、直方图按数值映射时用 */
export const sequential = ['#1d1e33', '#3b3d6b', '#6468b8', '#a3a7f0', '#d4d6ff']

/** 柱子的竖向渐变：顶亮底透，带一点玻璃感 */
export function barGradient(top: string = color.accent, alpha = 0.08) {
  return {
    type: 'linear' as const,
    x: 0,
    y: 0,
    x2: 0,
    y2: 1,
    colorStops: [
      { offset: 0, color: top },
      { offset: 1, color: `rgba(163, 167, 240, ${alpha})` },
    ],
  }
}

/** 横向条形的渐变：左暗右亮，像参考稿里的"市场份额"进度条 */
export function hbarGradient(right: string = color.accentBright) {
  return {
    type: 'linear' as const,
    x: 0,
    y: 0,
    x2: 1,
    y2: 0,
    colorStops: [
      { offset: 0, color: 'rgba(163, 167, 240, 0.25)' },
      { offset: 1, color: right },
    ],
  }
}

/** 价格区间的固定配色与中文名：同一色系由浅到深，各图保持一致 */
export const priceBucketMeta: Record<PriceBucket, { label: string; color: string }> = {
  free: { label: '免费', color: '#e8e9f7' },
  lt10: { label: '$10 以下', color: '#c6c8fb' },
  '10_30': { label: '$10–30', color: '#a3a7f0' },
  '30_60': { label: '$30–60', color: '#7f84dc' },
  ge60: { label: '$60 及以上', color: '#5f63b4' },
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
  axisLine: { lineStyle: { color: 'rgba(227, 228, 242, 0.12)' } },
  axisTick: { show: false },
  axisLabel: { color: color.textSecondary, fontSize: font.axis },
  splitLine: { lineStyle: { color: color.grid, type: 'dashed' } },
  nameTextStyle: { color: color.textSecondary, fontSize: font.axis },
}

echarts.registerTheme(THEME_NAME, {
  color: palette,
  backgroundColor: 'transparent',
  textStyle: { fontFamily: FONT_FAMILY, color: color.text },
  title: { textStyle: { color: color.text } },
  legend: {
    textStyle: { color: color.text, fontSize: font.label },
    itemWidth: 16,
    itemHeight: 10,
    itemGap: 18,
    icon: 'roundRect',
  },
  tooltip: {
    backgroundColor: 'rgba(22, 23, 38, 0.78)',
    borderColor: 'rgba(255, 255, 255, 0.10)',
    borderRadius: 14,
    padding: [12, 16],
    textStyle: { color: color.text, fontSize: font.label },
    extraCssText: `font-family: ${FONT_FAMILY}; backdrop-filter: blur(16px) saturate(140%); box-shadow: 0 16px 40px rgba(0,0,0,0.5);`,
    axisPointer: {
      lineStyle: { color: 'rgba(227, 228, 242, 0.35)', type: 'solid' },
      shadowStyle: { color: 'rgba(163, 167, 240, 0.08)' },
      crossStyle: { color: 'rgba(227, 228, 242, 0.35)' },
    },
  },
  categoryAxis: { ...axisCommon, splitLine: { show: false } },
  valueAxis: axisCommon,
  timeAxis: axisCommon,
  visualMap: { textStyle: { color: color.textSecondary } },
  // 全局动画：更长、更柔的缓动，数据更新时平滑过渡
  animationDuration: 900,
  animationEasing: 'cubicOut',
  animationDurationUpdate: 700,
  animationEasingUpdate: 'cubicInOut',
})
