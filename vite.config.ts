import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  // For testing on a phone through an https tunnel (ngrok, cloudflared): tunnel port 5173, set VITE_API_URL= (empty) in .env.local so the app
  // calls /api on the same origin, and this proxy forwards it to the backend.
  server: {
    host: true,
    allowedHosts: true,
    proxy: { '/api': { target: 'http://localhost:8765', changeOrigin: true } },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
  },
  optimizeDeps: {
    exclude: ['lucide-react'],
  },
});
