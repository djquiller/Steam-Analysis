// 各接口 data 的类型，字段与 docs/api.md "data 结构"一一对应。

export type PriceBucket = 'free' | 'lt10' | '10_30' | '30_60' | 'ge60'

export interface FilterParams {
  year_start?: number
  year_end?: number
  genre?: string
  price_bucket?: string
}

export interface MetaFilters {
  years: { min: number | null; max: number | null }
  genres: { genre: string; game_cnt: number }[]
  price_buckets: { key: PriceBucket; label: string; game_cnt: number }[]
}

export interface MetaUpdatedAt {
  data_updated_at: string | null
  ccu_updated_at: string | null
  tables: { table: string; rows: number; updated_at: string }[]
}

export interface Kpi {
  game_cnt: number
  review_cnt: number | null
  owners_total: number
  online_peak_24h: number | null
  online_peak_at: string | null
  updated_at: string
}

export interface YearlyItem {
  year: number
  game_cnt: number
  price_sum: number
  avg_price_usd: number | null
}

export interface GenreHeatItem {
  genre: string
  game_cnt: number
  owners_sum: number
  review_cnt: number
  positive_cnt: number
  positive_rate: number | null
}

export interface PriceRatingBox {
  price_bucket: PriceBucket
  game_cnt: number
  min: number
  q1: number
  median: number
  q3: number
  max: number
}

export type TopMetric = 'owners' | 'ccu'

export interface TopSellerItem {
  rank: number
  appid: number
  name: string
  release_year: number
  price_usd: number
  owners_mid: number | null
  ccu_latest: number | null
  ccu_at: string | null
  peak_ccu: number | null
  review_cnt: number
  positive_rate: number | null
}

export interface OnlineLive {
  snapshot_at: string | null
  items: { rank: number; appid: number; name: string; player_count: number; player_count_prev: number | null }[]
}

export interface ClusterGames {
  total: number
  clusters: { cluster_id: number; cluster_label: string; game_cnt: number }[]
  points: {
    appid: number
    name: string
    cluster_id: number
    x: number
    y: number
    price_usd: number
    positive_rate: number
    owners_mid: number
  }[]
}

export interface RatingDist {
  bin_width: number
  game_cnt: number
  bins: { bin_start: number; bin_end: number; game_cnt: number }[]
}

export interface ReviewLanguages {
  review_cnt: number
  items: {
    language: string
    review_cnt: number
    positive_cnt: number
    positive_rate: number | null
    share: number | null
  }[]
}

export interface PlaytimeDist {
  review_cnt: number
  bins: { bin: number; min_hours: number; max_hours: number | null; review_cnt: number }[]
}

export interface ActivityHeatmap {
  timezone: string
  review_cnt: number
  max_cnt: number
  cells: { weekday: number; hour: number; review_cnt: number }[]
}

export interface GameDetail {
  appid: number
  name: string
  header_image: string | null
  release_date: string | null
  release_year: number | null
  price_usd: number
  price_bucket: PriceBucket
  genres: string[]
  developer: string | null
  publisher: string | null
  owners_low: number | null
  owners_high: number | null
  owners_mid: number | null
  peak_ccu: number | null
  review_cnt: number
  positive_cnt: number
  positive_rate: number | null
  avg_playtime_min: number | null
  median_playtime_min: number | null
  metacritic_score: number | null
  required_age: number | null
  dlc_count: number | null
  achievements: number | null
  num_languages: number | null
  platforms: string[]
  cluster: { cluster_id: number; cluster_label: string } | null
  hot_pred: { hot_prob: number; hot_pred: boolean; hot_actual: boolean; is_test: boolean; model_name: string } | null
  sentiment: { sample_cnt: number; positive_cnt: number; positive_ratio: number | null; method: string } | null
  peers: {
    cluster_id: number
    cluster_label: string
    game_cnt: number
    avg_price_usd: number
    avg_positive_rate: number
    avg_owners_mid: number
    avg_playtime_min: number
  } | null
}

export interface ReviewTrendItem {
  month: string
  review_cnt: number
  positive_cnt: number
  positive_rate: number | null
}

export interface PricePoint {
  date: string
  price_usd: number
}
