//No tocar este archivo
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { NodeGlobalsPolyfillPlugin } from '@esbuild-plugins/node-globals-polyfill';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/', 

  server: {
    proxy: {
      '/api': {
        target: 'https://h6ysn7u0t1.execute-api.us-east-1.amazonaws.com/dev2',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
        secure: false
      }
    }
  },

  build: {
    target: 'es2020',
    modulePreload: {
      polyfill: false, 
    },
    chunkSizeWarningLimit: 2000, 
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('@aws-sdk')) return 'vendor_aws_sdk';
            if (id.includes('react-quill') || id.includes('quill')) return 'vendor_quill';
            if (id.includes('react') || id.includes('react-dom')) return 'vendor_react';
            return 'vendor_misc';
          }
        }
      }
    }
  },

  optimizeDeps: {
    esbuildOptions: {
      target: 'es2020',
      define: {
        global: 'globalThis', 
      },
      plugins: [
        NodeGlobalsPolyfillPlugin({
          buffer: true,
        }),
      ],
    },
  },
});
