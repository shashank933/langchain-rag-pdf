import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  define: {
    'import.meta.env.DEFAULT_USERNAME': JSON.stringify(process.env.DEFAULT_USERNAME),
    'import.meta.env.DEFAULT_PASSWORD': JSON.stringify(process.env.DEFAULT_PASSWORD),
  },
});
