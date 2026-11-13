// 数字与时间的显示格式。所有图表、卡片都从这里取，保证全屏口径一致。

/** 大数用中文单位：1.05 亿、3.2 万；null 显示 "—" */
export function bigNum(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—'
  const abs = Math.abs(v)
  if (abs >= 1e8) return `${trim((v / 1e8).toFixed(digits))} 亿`
  if (abs >= 1e4) return `${trim((v / 1e4).toFixed(digits))} 万`
  return v.toLocaleString('zh-CN')
}

/** 千分位整数 */
export function intNum(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—'
  return Math.round(v).toLocaleString('zh-CN')
}

/** 0–1 的比率显示为百分比 */
export function pct(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined) return '—'
  return `${(v * 100).toFixed(digits)}%`
}

export function usd(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—'
  return v === 0 ? '免费' : `$${v.toFixed(2)}`
}

/** ISO 时间（UTC，带 Z）→ 本地时间 "MM-DD HH:mm" 或 "YYYY-MM-DD HH:mm" */
export function dateTime(iso: string | null | undefined, withYear = false): string {
  if (!iso) return '—'
  const d = new Date(iso)
  const p = (n: number) => String(n).padStart(2, '0')
  const md = `${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
  return withYear ? `${d.getFullYear()}-${md}` : md
}

/** 分钟 → "12.5 小时" */
export function hours(min: number | null | undefined): string {
  if (min === null || min === undefined) return '—'
  return `${trim((min / 60).toFixed(1))} 小时`
}

function trim(s: string): string {
  return s.includes('.') ? s.replace(/\.?0+$/, '') : s
}

export const WEEKDAYS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
