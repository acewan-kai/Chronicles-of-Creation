import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// API服务器地址
const API_BASE = 'http://170.106.194.111:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: API_BASE,
        changeOrigin: true
      }
    }
  }
})
