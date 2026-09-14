// Real localhost integration smoke. Credentials are captured only in memory;
// no trace, video, auth screenshots or account values are written to disk.
import { execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const require = createRequire(path.join(root, 'apps/web/package.json'));
const { chromium, expect, devices } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;
const compose = ['compose', '-f', 'docker-compose.yml', '-f', 'compose.ai.yml', '-f', 'compose.monitoring.yml', '--profile', 'monitoring', '--profile', 'sensors'];
const raw = execFileSync('docker', [...compose, 'exec', '-T', '--user', 'root', 'api', 'python', '-c',
  'import json; print(json.dumps(json.load(open("/run/roadsignal/accounts.json"))["roadsignal"]))'],
  { cwd: root, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true });
const account = JSON.parse(raw);
const output = path.join(root, '.codex-finish/monitoring-review');
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true, args: ['--enable-unsafe-swiftshader'] });
try {
  for (const [name, viewport] of [['desktop', { viewport: { width: 1440, height: 1000 } }], ['mobile', devices['Pixel 7']]]) {
    const context = await browser.newContext({ ...viewport, reducedMotion: 'reduce' });
    const page = await context.newPage();
    page.setDefaultTimeout(30_000);
    // Keep unrelated entry video out of the local integration check.
    await page.route('**/*.mp4', route => route.abort());
    await page.goto('http://localhost:3000/');
    await page.getByLabel('Email', { exact: true }).fill(account.email);
    await page.getByLabel('Password', { exact: true }).fill(account.password);
    await page.getByRole('button', { name: 'Sign in securely' }).click();
    await page.getByRole('button', { name: 'Open fleet replay' }).click();
    await page.getByRole('button', { name: 'Connected demo', exact: true }).click();
    await expect(page.getByRole('button', { name: 'Vehicle trackers 4' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Street sensors 3' })).toBeVisible();
    const monitor = page.locator('.fleet-monitor');
    await expect(monitor).toHaveAttribute('data-playing', 'false');
    await page.getByRole('button', { name: 'Street sensors 3' }).click();
    await page.getByRole('list', { name: 'Demo street sensors' }).getByRole('button', { name: /Athlone station/ }).click();
    await expect(page.getByRole('region', { name: 'Selected device details' })).toContainText('Road surface');
    await page.getByText('Saved daily summaries', { exact: true }).click();
    await page.getByRole('button', { name: 'Load saved reports' }).click();
    await expect(page.locator('.daily-reports tbody tr').first()).toBeVisible();
    expect(await page.locator('.daily-reports tbody tr').count()).toBeLessThanOrEqual(31);
    await page.getByText('Evidence review inbox', { exact: true }).click();
    await page.getByRole('button', { name: 'Load pending evidence' }).click();
    await expect(page.locator('.evidence-entry').first()).toContainText('Synthetic demonstration');
    await page.getByText('Traffic frame check', { exact: true }).click();
    await expect(page.getByRole('button', { name: 'Run blank demo frame' })).toBeEnabled();
    await page.getByRole('button', { name: 'Run blank demo frame' }).click();
    await expect(page.getByRole('heading', { name: 'Synthetic frame result' })).toBeVisible({ timeout: 100_000 });
    for (const count of await page.locator('.frame-result dd').allTextContents()) {
      expect(count).toBe('0');
    }
    const audit = await new AxeBuilder({ page }).include('.fleet-monitor').withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
    expect(audit.violations.map(v => ({ id: v.id, targets: v.nodes.map(n => n.target) }))).toEqual([]);
    expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1)).toBe(false);
    await monitor.screenshot({ path: path.join(output, `${name}.png`), style: '.shell > aside { visibility: hidden !important; }' });
    console.log(`PASS ${name}: actual operator login, 7 devices, daily reports, evidence inbox, CPU vision, accessibility and no horizontal overflow`);
    await context.close();
  }
} catch (error) {
  // A failed fill action may echo its value. Never print the local password.
  console.error(String(error).split(account.password).join('[redacted]'));
  process.exitCode = 1;
} finally {
  await browser.close();
}
