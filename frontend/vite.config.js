import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig(({ mode }) => {
  const rootEnv = loadEnv(mode, path.resolve(__dirname, '..'), '');

  return {
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
      'import.meta.env.DEFAULT_USERNAME': JSON.stringify(rootEnv.DEFAULT_USERNAME),
      'import.meta.env.DEFAULT_PASSWORD': JSON.stringify(rootEnv.DEFAULT_PASSWORD),
    },
  };
});
