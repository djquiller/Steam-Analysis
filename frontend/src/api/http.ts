import axios, { AxiosError } from 'axios'

/**
 * 后端统一返回 {code, msg, data}（docs/api.md "返回信封"）。
 * 这里把信封解包：code = 0 直接返回 data；否则抛 ApiError，组件只需处理一种错误。
 * 后端出错时 HTTP 状态码是 400/404/500，响应体里同样带 code 与 msg，所以失败分支也要读 body。
 */
export class ApiError extends Error {
  constructor(
    public code: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

interface Envelope<T> {
  code: number
  msg: string
  data: T
}

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || '/api/v1',
  timeout: 15000,
})

export async function get<T>(url: string, params?: object, signal?: AbortSignal): Promise<T> {
  try {
    const res = await http.get<Envelope<T>>(url, { params, signal })
    if (res.data.code !== 0) throw new ApiError(res.data.code, res.data.msg)
    return res.data.data
  } catch (e) {
    if (e instanceof ApiError || axios.isCancel(e)) throw e
    const err = e as AxiosError<Envelope<unknown>>
    const body = err.response?.data
    if (body && typeof body.code === 'number') throw new ApiError(body.code, body.msg)
    if (err.code === 'ECONNABORTED') throw new ApiError(-1, '请求超时')
    // 响应体不是信封：后端没起来（开发时 Vite 代理连不上会回 500/502）或网关出错
    const status = err.response?.status
    if (!status || status >= 500) throw new ApiError(-1, `后端服务不可用${status ? `（HTTP ${status}）` : ''}`)
    throw new ApiError(-1, `请求失败（HTTP ${status}）`)
  }
}

export function isCancel(e: unknown): boolean {
  return axios.isCancel(e)
}
