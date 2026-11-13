import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import { defineConfig, loadEnv } from 'vite'

// 开发时把 /api 与 /health 代理到 FastAPI（默认 127.0.0.1:8000），前端代码只写相对路径，不用处理跨域。
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, fileURLToPath(new URL('.', import.meta.url)), '')
  const backend = env.VITE_BACKEND_URL || 'http://127.0.0.1:8000'
  return {
    plugins: [vue()],
    resolve: {
      alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
    },
    server: {
      port: 5173,
      host: '127.0.0.1',
      proxy: {
        '/api': { target: backend, changeOrigin: true },
        '/health': { target: backend, changeOrigin: true },
      },
    },
    build: {
      chunkSizeWarningLimit: 1200, // echarts 按需引入后约 1 MB，属预期
    },
  }
})
