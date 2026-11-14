/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** 接口前缀；默认 /api/v1（开发时由 Vite 代理到后端） */
  readonly VITE_API_BASE?: string
  /** 开发代理的后端地址，只在 vite.config.ts 里用 */
  readonly VITE_BACKEND_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
