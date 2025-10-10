//No tocar este archivo
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { NodeGlobalsPolyfillPlugin } from '@esbuild-plugins/node-globals-polyfill';

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/', // importante para rutas relativas en Amplify

  // 🔧 Evitar que Vite/ESBuild inserte top-level await en el bundle
  build: {
    target: 'es2020',
    modulePreload: {
      polyfill: false, // no generar preloads que requieran TLA
    },
    // Increase the chunk size warning limit and add manualChunks for large deps
    chunkSizeWarningLimit: 2000, // kB
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
        global: 'globalThis', // 👈 esto soluciona tu error de "global"
      },
      plugins: [
        NodeGlobalsPolyfillPlugin({
          buffer: true,
        }),
      ],
    },
  },
});
