import {defineConfig} from 'vite';

export default defineConfig({
  server: {
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
