import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    proxy: {
      '/state': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/history': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/scheme': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/equipment': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/action': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/input': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/scenario': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/failure': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/alarms': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/simulation': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/command': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/controllers': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/training': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/lms': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/auth': { target: 'http://127.0.0.1:8000', changeOrigin: true },
      '/ws': { target: 'ws://127.0.0.1:8000', ws: true },
    },
  },
});
