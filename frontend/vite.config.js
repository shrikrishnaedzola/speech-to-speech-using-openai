import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// /api requests are forwarded to the FastAPI backend, so the browser
// only ever talks to our own server (never directly with the API key).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    // API_TARGET lets you point at a backend on another port (default 8000).
    proxy: { '/api': process.env.API_TARGET || 'http://127.0.0.1:8000' },
  },
})
