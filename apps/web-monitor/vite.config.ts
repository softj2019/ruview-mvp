import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5280,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8001',
        ws: true,
      },
      '/health': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      '/cam': {
        target: 'http://localhost:8002',
        changeOrigin: true,
      },
    },
  },
});
