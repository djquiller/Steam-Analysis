/**
 * 字体：只用随前端打包的本地无衬线字体，不依赖系统字体，也不从 CDN 加载。
 * 这样任何电脑（包括断网的答辩现场）看到的字形都一样。
 *
 * - Inter（拉丁字母与数字，只引 latin 子集）：数字等宽对齐好看，KPI 用 tabular-nums
 * - Noto Sans SC 思源黑体（中文）：每个字重按 unicode-range 切成约 100 个小文件，
 *   浏览器只下载页面上实际出现的字所在的分片
 * 两者都是 SIL OFL 1.1 许可，可随项目分发。
 */
import '@fontsource/inter/latin-400.css'
import '@fontsource/inter/latin-600.css'
import '@fontsource/inter/latin-700.css'
import '@fontsource/noto-sans-sc/400.css'
import '@fontsource/noto-sans-sc/700.css'

/** 拉丁字符走 Inter，中文落到 Noto Sans SC；最后的 sans-serif 只是字体文件还没下载完时的占位 */
export const FONT_FAMILY = "'Inter', 'Noto Sans SC', sans-serif"
