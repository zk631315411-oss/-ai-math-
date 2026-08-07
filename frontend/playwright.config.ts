import { defineConfig, devices } from '@playwright/test';

const python = process.env.AI_MATH_PYTHON || '.\\venv\\Scripts\\python.exe';
const apiPort = Number(process.env.PLAYWRIGHT_API_PORT || 8010);
const appPort = Number(process.env.PLAYWRIGHT_APP_PORT || 5174);

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
    baseURL: `http://127.0.0.1:${appPort}`,
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
      command: `${python} -m uvicorn app.main:app --host 127.0.0.1 --port ${apiPort}`,
      cwd: '..',
      env: {
        AI_MATH_DB_PATH: 'data/playwright-learning.db',
        DIAGNOSIS_V2_MODE: 'shadow',
      },
      port: apiPort,
      timeout: 30_000,
      reuseExistingServer: false,
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${appPort}`,
      env: {
        VITE_API_BASE: `http://127.0.0.1:${apiPort}/api`,
      },
      port: appPort,
      timeout: 30_000,
      reuseExistingServer: !process.env.CI,
    },
  ],
});
