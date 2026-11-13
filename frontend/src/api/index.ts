// 按 docs/api.md 分组的请求函数。可筛选接口统一接收 FilterParams（由 stores/filters.ts 生成）。
import { get } from './http'
import type {
  ActivityHeatmap,
  ClusterGames,
  FilterParams,
  GameDetail,
  GenreHeatItem,
  Kpi,
  MetaFilters,
  MetaUpdatedAt,
  OnlineLive,
  PlaytimeDist,
  PricePoint,
  PriceRatingBox,
  RatingDist,
  ReviewLanguages,
  ReviewTrendItem,
  TopMetric,
  TopSellerItem,
  YearlyItem,
} from './types'

type S = AbortSignal | undefined

export const metaApi = {
  filters: (s?: S) => get<MetaFilters>('/meta/filters', undefined, s),
  updatedAt: (s?: S) => get<MetaUpdatedAt>('/meta/updated-at', undefined, s),
}

export const overviewApi = {
  // 表里还没有数据时后端返回 {}
  kpi: (s?: S) => get<Kpi | Record<string, never>>('/overview/kpi', undefined, s),
}

export const trendApi = {
  yearly: (f: FilterParams, s?: S) => get<YearlyItem[]>('/trend/yearly', f, s),
  genres: (f: FilterParams, s?: S) => get<GenreHeatItem[]>('/trend/genres', f, s),
  priceRating: (f: FilterParams, s?: S) => get<PriceRatingBox[]>('/trend/price-rating', f, s),
}

export const rankApi = {
  topSellers: (f: FilterParams & { metric: TopMetric; limit?: number }, s?: S) =>
    get<TopSellerItem[]>('/rank/top-sellers', f, s),
  onlineLive: (limit = 20, s?: S) => get<OnlineLive>('/rank/online-live', { limit }, s),
}

export const clusterApi = {
  games: (f: FilterParams & { limit?: number }, s?: S) => get<ClusterGames>('/cluster/games', f, s),
}

export const ecosystemApi = {
  ratingDist: (f: FilterParams & { bin_width?: number }, s?: S) => get<RatingDist>('/ecosystem/rating-dist', f, s),
  reviewLanguages: (f: FilterParams & { limit?: number }, s?: S) =>
    get<ReviewLanguages>('/ecosystem/review-languages', f, s),
  playtimeDist: (f: FilterParams, s?: S) => get<PlaytimeDist>('/ecosystem/playtime-dist', f, s),
  activityHeatmap: (f: FilterParams, s?: S) => get<ActivityHeatmap>('/ecosystem/activity-heatmap', f, s),
}

export const gamesApi = {
  detail: (appid: number, s?: S) => get<GameDetail>(`/games/${appid}`, undefined, s),
  reviewsTrend: (appid: number, s?: S) => get<ReviewTrendItem[]>(`/games/${appid}/reviews-trend`, undefined, s),
  priceHistory: (appid: number, s?: S) => get<PricePoint[]>(`/games/${appid}/price-history`, undefined, s),
}
