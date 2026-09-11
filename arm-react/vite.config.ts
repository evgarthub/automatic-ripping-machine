import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const proxyTarget = process.env.VITE_DEV_PROXY_TARGET ?? 'http://localhost:8080'

// https://vite.dev/config/
export default defineConfig({
  base: '/app/',
  plugins: [react()],
  server: {
    proxy: {
      '/api/v1': {
        target: proxyTarget,
        changeOrigin: true,
        ws: true,
      },
      '/socket.io': {
        target: proxyTarget,
        changeOrigin: true,
        ws: true,
      },
    },
  },
})
