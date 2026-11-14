import { onBeforeUnmount, ref, shallowRef, watch, type Ref, type WatchSource } from 'vue'

import { ApiError, isCancel } from '@/api/http'

export type RemoteState = 'loading' | 'ready' | 'error'

/** 失败后自动重试的间隔（毫秒），逐次加长；参数错误这类重试也没用的不重试 */
const RETRY_DELAYS = [5_000, 15_000, 30_000, 60_000]

/**
 * 请求一个接口并跟踪三态。
 * - 依赖（如筛选参数）变化时自动重新请求，并取消上一次还没回来的请求；
 * - 请求失败时保留上一次成功的数据作为降级，同时给出错误信息（frontend/CLAUDE.md "三态"）；
 * - 后端暂时不可用时按 5 / 15 / 30 / 60 秒自动重试，后端恢复后各图自己好起来，不用逐个点"重试"；
 * - pollMs > 0 时定时刷新（实时在线榜用）。
 */
export function useRemote<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  deps: WatchSource[] = [],
  opts: { pollMs?: number } = {},
) {
  const data = shallowRef<T | null>(null) as Ref<T | null>
  const state = ref<RemoteState>('loading')
  const error = ref<string | null>(null)
  let controller: AbortController | null = null
  let timer: ReturnType<typeof setInterval> | null = null
  let retryTimer: ReturnType<typeof setTimeout> | null = null
  let failures = 0

  async function load() {
    if (retryTimer) clearTimeout(retryTimer)
    retryTimer = null
    controller?.abort()
    const c = new AbortController()
    controller = c
    state.value = 'loading'
    try {
      const result = await fetcher(c.signal)
      if (c.signal.aborted) return
      data.value = result
      error.value = null
      state.value = 'ready'
      failures = 0
    } catch (e) {
      if (isCancel(e) || c.signal.aborted) return
      error.value = e instanceof ApiError ? e.message : '加载失败'
      state.value = 'error'
      // 40001 / 40401 是请求本身的问题，重试结果不会变
      const retryable = !(e instanceof ApiError) || e.code < 0 || e.code >= 50000
      if (retryable) {
        const delay = RETRY_DELAYS[Math.min(failures, RETRY_DELAYS.length - 1)]
        failures += 1
        retryTimer = setTimeout(load, delay)
      }
    }
  }

  // 依赖变化（换筛选条件）视为新请求，重试计数清零
  watch(deps, () => {
    failures = 0
    load()
  }, { deep: true, immediate: true })
  if (opts.pollMs) timer = setInterval(load, opts.pollMs)

  onBeforeUnmount(() => {
    controller?.abort()
    if (timer) clearInterval(timer)
    if (retryTimer) clearTimeout(retryTimer)
  })

  return { data, state, error, reload: load }
}
