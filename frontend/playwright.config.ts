import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/specs',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : 3,
  reporter: [
    ['html', { outputFolder: '../playwright-report' }],
    ['list'],
  ],
  timeout: 180_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: 'http://127.0.0.1:5174',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 15_000,
  },
  projects: [
    {
      name: 'chromium-desktop',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } },
    },
    {
      name: 'chromium-mobile',
      use: { ...devices['Pixel 5'], viewport: { width: 390, height: 844 } },
    },
  ],
  webServer: [
    {
      command: '.\\venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8010',
      cwd: '..',
      env: {
        AI_MATH_DB_PATH: 'data/playwright-learning.db',
        DIAGNOSIS_V2_MODE: 'shadow',
      },
      port: 8010,
      timeout: 30_000,
      reuseExistingServer: false,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 5174',
      env: {
        VITE_API_BASE: 'http://127.0.0.1:8010/api',
      },
      port: 5174,
      timeout: 30_000,
      reuseExistingServer: false,
    },
  ],
});
