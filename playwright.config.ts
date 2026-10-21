import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  tsconfig: './tsconfig.tests.json',
  testDir: './tests/e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 2 : 3,
  timeout: 45_000,
  expect: { timeout: 15_000 },
  outputDir: 'output/playwright/test-results',
  reporter: [['list'], ['html', { outputFolder: 'output/playwright/report', open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:4173/dataguard/',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    serviceWorkers: 'block',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
    { name: 'mobile-chromium', use: { ...devices['Pixel 7'] } },
  ],
  webServer: {
    command: 'pnpm exec vite --host 127.0.0.1 --port 4173 --strictPort --mode e2e',
    url: 'http://127.0.0.1:4173/dataguard/',
    reuseExistingServer: false,
    env: { VITE_DATA_SOURCE: 'api', VITE_API_BASE_URL: '/api/v1' },
  },
})
