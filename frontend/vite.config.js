import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,  // Cho phép máy khác trong mạng LAN truy cập
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8001',
        ws: true,
        changeOrigin: true,
      },
      '/stream': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    // Tối ưu #9: Chunk splitting
    sourcemap: false,  // Tắt sourcemap cho prod (giảm ~40% build size)
    rollupOptions: {
      output: {
        manualChunks: {
          // Tách vendor chunks — cache riêng biệt
          'vendor-react': ['react', 'react-dom'],
          'vendor-router': ['react-router-dom'],
          'vendor-charts': ['recharts'],
          'vendor-state': ['zustand'],
        },
      },
    },
    // Cảnh báo chunk > 300KB
    chunkSizeWarningLimit: 300,
  },
})
