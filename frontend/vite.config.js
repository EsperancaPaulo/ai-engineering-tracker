import {fileURLToPath} from 'node:url';
import {defineConfig} from 'vite';

export default defineConfig({
  server: {
    fs: {allow:[fileURLToPath(new URL('.',import.meta.url)),fileURLToPath(new URL('../shared',import.meta.url))]},
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/auth': 'http://127.0.0.1:8000',
      '/me': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
    },
  },
  build: {sourcemap: false},
  test: {environment: 'jsdom', setupFiles: ['./src/tests/setup.js'], clearMocks: true},
});
