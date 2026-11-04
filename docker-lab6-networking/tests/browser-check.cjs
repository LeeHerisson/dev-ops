// Optional browser check. Install Playwright or set PLAYWRIGHT_MODULE to its module path.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

(async () => {
  const launchOptions = { headless: true };
  if (process.env.CHROMIUM_EXECUTABLE) launchOptions.executablePath = process.env.CHROMIUM_EXECUTABLE;
  const browser = await chromium.launch(launchOptions);
  const root = path.resolve(__dirname, '..');
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const failures = [];
  page.on('pageerror', error => failures.push(error.message));
  const checks = [];
  try {
    await page.goto('http://127.0.0.1:' + (process.env.FRONTEND_PORT || '8080'), {waitUntil: 'networkidle'});
    await page.getByRole('button', {name: 'Очистить корзину'}).click();
    await page.locator('#cart-total').filter({hasText: '$0'}).waitFor();
    const cards = page.locator('#products article');
    assert.equal(await cards.count(), 3);
    checks.push('Three product cards loaded from the live API');
    await cards.filter({hasText: 'Docker T-Shirt'}).getByRole('button').click();
    await page.locator('#cart-total').filter({hasText: '$25'}).waitFor();
    await cards.filter({hasText: 'Kubernetes Mug'}).getByRole('button').click();
    await page.locator('#cart-total').filter({hasText: '$40'}).waitFor();
    assert.equal((await page.locator('#cart-count').textContent()).trim(), '2');
    assert.equal(await page.locator('#cart-items li').count(), 2);
    checks.push('UI adds two products and shows count=2, total=$40');
    await page.screenshot({path: path.join(root, 'evidence', 'shop-desktop.png'), fullPage: true});
    await page.setViewportSize({width: 390, height: 844});
    await page.screenshot({path: path.join(root, 'evidence', 'shop-mobile.png'), fullPage: false});
    const dimensions = await page.evaluate(() => ({scroll: document.documentElement.scrollWidth, viewport: innerWidth}));
    assert.ok(dimensions.scroll <= dimensions.viewport, 'mobile horizontal overflow');
    assert.deepEqual(failures, []);
    checks.push('Mobile layout has no horizontal overflow; no JavaScript page errors');
    fs.writeFileSync(path.join(root, 'evidence', 'browser-check.json'),
      JSON.stringify({passed: true, measured_at_utc: new Date().toISOString(), checks, dimensions, page_errors: failures}, null, 2) + '\n');
    console.log(JSON.stringify({passed: true, checks: checks.length}));
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
