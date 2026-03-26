import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 3000,
    cors: true,
    proxy: {
      '/api':         { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/health':      { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/forms':       { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/detect':      { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/extract':     { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/validate':    { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/apply-fixes': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/revalidate':  { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/enums':       { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/clients':     { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/ledger':      { target: 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
