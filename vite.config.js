//No tocar este archivo
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

import { NodeGlobalsPolyfillPlugin } from '@esbuild-plugins/node-globals-polyfill'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  base: '/', // importante para rutas relativas en Amplify
  optimizeDeps: {
    esbuildOptions: {
      define: {
        global: 'globalThis', // 👈 esto soluciona tu error
      },
      plugins: [
        NodeGlobalsPolyfillPlugin({
          buffer: true,
        }),
      ],
    },
  },
})