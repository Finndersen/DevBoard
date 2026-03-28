/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    globals: true,
    environment: 'happy-dom',
    setupFiles: ['./src/test/preSetup.ts', './src/test/setup.ts'],
    env: {
      VITE_API_BASE_URL: 'http://localhost:8000',
    },
    onConsoleLog: () => false,
  },
})