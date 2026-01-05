import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@components': path.resolve(__dirname, './src/components'),
      '@pages': path.resolve(__dirname, './src/pages'),
      '@resources': path.resolve(__dirname, './src/resources'),
      '@providers': path.resolve(__dirname, './src/providers'),
      '@api': path.resolve(__dirname, './src/api'),
    },
  },
  server: {
    port: 3000,
    host: '0.0.0.0', // 允许外部访问
    proxy: {
      '/api': {
        target: 'http://localhost:8083',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8083',
        ws: true,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          // React core libraries
          if (id.includes('node_modules/react') || id.includes('node_modules/react-dom')) {
            return 'vendor-react';
          }

          // Ant Design and icons
          if (id.includes('node_modules/antd') || id.includes('node_modules/@ant-design')) {
            return 'vendor-antd';
          }

          // Refine framework
          if (id.includes('node_modules/@refinedev')) {
            return 'vendor-refine';
          }

          // React Router
          if (id.includes('node_modules/react-router-dom') || id.includes('node_modules/react-router')) {
            return 'vendor-router';
          }

          // Charting libraries (recharts, tremor)
          if (id.includes('node_modules/recharts') || id.includes('node_modules/@tremor')) {
            return 'vendor-charts';
          }

          // Icon libraries (separate from antd for better caching)
          if (id.includes('node_modules/@iconify') ||
              id.includes('node_modules/@ant-design/icons-svg')) {
            return 'vendor-icons';
          }

          // Other large dependencies (axios, dayjs, etc.)
          if (id.includes('node_modules/axios') ||
              id.includes('node_modules/dayjs') ||
              id.includes('node_modules/lodash')) {
            return 'vendor-utils';
          }

          // All other node_modules
          if (id.includes('node_modules')) {
            return 'vendor-common';
          }
        },
        // Optimize chunk file names
        chunkFileNames: 'assets/[name]-[hash].js',
        entryFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash].[ext]',
      },
    },
    // Increase chunk size warning limit to 600kb (some vendor chunks are legitimately large)
    chunkSizeWarningLimit: 600,
  },
});
