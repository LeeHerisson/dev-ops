// Capture actual GET responses from the running API, without generated mock data.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const root = path.resolve(__dirname, '..');
  const settings = Object.fromEntries(fs.readFileSync(path.join(root, '.env'), 'utf8')
    .split('\n').filter(line => line && !line.startsWith('#')).map(line => line.split(/=(.*)/s).slice(0, 2)));
  const browser = await chromium.launch({headless: true,
    ...(process.env.CHROMIUM_EXECUTABLE ? {executablePath: process.env.CHROMIUM_EXECUTABLE} : {})});
  const page = await browser.newPage({viewport: {width: 1280, height: 800}});
  const pages = [];
  try {
    for (const [endpoint, name] of [['/health','health'], ['/db-test','database'],
                                   ['/cache-test','cache'], ['/users','users']]) {
      const response = await page.goto('http://127.0.0.1:' + (settings.API_PORT || '5059') + endpoint,
                                       {waitUntil: 'networkidle'});
      if (response.status() !== 200) throw new Error(endpoint + ' returned ' + response.status());
      await page.screenshot({path: path.join(root, 'evidence', 'api-' + name + '.png')});
      pages.push({endpoint, status: response.status(), screenshot: 'api-' + name + '.png'});
    }
    fs.writeFileSync(path.join(root, 'evidence', 'browser-evidence.json'),
      JSON.stringify({measured_at_utc: new Date().toISOString(), pages}, null, 2) + '\n');
    console.log(JSON.stringify({captured: pages.length}));
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error);process.exitCode=1;});
