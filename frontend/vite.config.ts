import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // AICAM_API_URL lets the e2e tests point at their own backend instance.
      '/api': process.env.AICAM_API_URL ?? 'http://127.0.0.1:8000',
    },
  },
})
