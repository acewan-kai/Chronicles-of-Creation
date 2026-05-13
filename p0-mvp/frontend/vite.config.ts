import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// API服务器地址 - 开发环境用本地，生产环境用远程
const API_BASE = 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: API_BASE,
        changeOrigin: true
      },
      '/worlds': {
        target: API_BASE,
        changeOrigin: true
      },
      '/books': {
        target: API_BASE,
        changeOrigin: true
      },
      '/templates': {
        target: API_BASE,
        changeOrigin: true
      },
      '/simulate': {
        target: API_BASE,
        changeOrigin: true
      },
      '/info': {
        target: API_BASE,
        changeOrigin: true
      },
      '/health': {
        target: API_BASE,
        changeOrigin: true
      }
    }
  }
})
