import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  base: '/studio/',
  plugins: [react(), tailwindcss()],
  build: {
    outDir: '../src/kater/web/studio_dist',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        entryFileNames: 'assets/studio.js',
        chunkFileNames: 'assets/chunk-[hash].js',
        assetFileNames: 'assets/studio.[ext]',
      },
    },
  },
  server: {
    port: 4318,
    proxy: {
      '/api': 'http://127.0.0.1:9091',
      '/health': 'http://127.0.0.1:9091',
    },
  },
});
