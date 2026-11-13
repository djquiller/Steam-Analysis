// ECharts 按需引入：只注册大屏用到的图表与组件，打包体积比整包小一半以上。
import { BarChart, BoxplotChart, HeatmapChart, LineChart, ScatterChart, TreemapChart } from 'echarts/charts'
import {
  DatasetComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TooltipComponent,
  VisualMapComponent,
} from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'

import '@/theme/steam-dark'

echarts.use([
  BarChart,
  BoxplotChart,
  HeatmapChart,
  LineChart,
  ScatterChart,
  TreemapChart,
  DatasetComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TooltipComponent,
  VisualMapComponent,
  CanvasRenderer,
])

export { echarts }
export type { EChartsCoreOption as ChartOption } from 'echarts/core'
