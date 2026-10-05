import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: { extensions: ['.ts', '.tsx', '.mjs', '.js', '.jsx', '.json'] },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8100',
      '/ws': { target: 'ws://127.0.0.1:8100', ws: true },
      '/metrics': 'http://127.0.0.1:8100'
    }
  }
})
