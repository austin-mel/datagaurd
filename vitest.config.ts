import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  test: {
    include: ['tests/unit/**/*.test.ts'],
    environment: 'node',
    restoreMocks: true,
    unstubGlobals: true,
    unstubEnvs: true,
    testTimeout: 30_000,
    coverage: {
      provider: 'v8',
      include: ['src/{services,stores,composables,utils}/**/*.ts', 'src/components/**/*.vue'],
      exclude: ['**/index.ts'],
      reporter: ['text', 'html', 'lcov'],
      thresholds: { statements: 90, branches: 80, functions: 85, lines: 90 },
    },
  },
})
