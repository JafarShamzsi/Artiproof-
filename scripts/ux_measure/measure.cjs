/* Run from repo root. Uses only this worktree's installed Playwright.
 * UX_OUTPUT must be an external artifact directory. No server is started here.
 */
const { chromium } = require('../../frontend/node_modules/@playwright/test');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const { execFileSync } = require('node:child_process');
const { calculateCls } = require('./cls.cjs');

const base = process.env.UX_BASE_URL || 'http://127.0.0.1:3204';
if (new URL(base).hostname !== '127.0.0.1') throw Error('Loopback only');
const output = process.env.UX_OUTPUT;
if (!output || !path.isAbsolute(output)) throw Error('Set absolute UX_OUTPUT');
fs.mkdirSync(output, { recursive: true });
const runs = Number(process.env.UX_RUNS || 3);
const windowMs = Number(process.env.UX_WINDOW_MS || 10000);
if (!Number.isInteger(runs) || runs < 1 || runs > 10) throw Error('UX_RUNS must be 1..10');
if (!Number.isFinite(windowMs) || windowMs < 1000 || windowMs > 60000) throw Error('UX_WINDOW_MS must be 1000..60000');

// Node http does not decompress: this is an independent, explicitly identified
// raw compressed-body probe, not a second measurement of browser wire traffic.
function rawProbe(url) {
  return new Promise((resolve, reject) => {
    const request = http.get(url, { headers: { 'Accept-Encoding': 'gzip, deflate, br' } }, res => {
      let bytes = 0;
      res.on('data', chunk => { bytes += chunk.length; });
      res.on('end', () => resolve({ url, status: res.statusCode, headers: res.headers,
        rawCompressedBodyBytes: bytes, excludes: 'HTTP headers, chunk framing, TCP/IP' }));
      res.on('error', reject);
    }).on('error', reject);
    request.setTimeout(30000, () => request.destroy(Error('Raw font probe timeout')));
  });
}

(async () => {
  const buildId = fs.readFileSync(path.join(__dirname, '../../frontend/.next/BUILD_ID'), 'utf8').trim();
  const fontManifest = JSON.parse(fs.readFileSync(path.join(__dirname, '../../frontend/.next/server/next-font-manifest.json'), 'utf8'));
  const sourceSHA = execFileSync('git', ['rev-parse', 'HEAD']).toString().trim();
  const browser = await chromium.launch({ headless: true });
  const report = { sourceSHA,
    measuredAt: new Date().toISOString(), browser: browser.version(), node: process.version,
    platform: process.platform, base, windowMs, reducedMotion: 'no-preference',
    buildLabel: process.env.UX_BUILD_LABEL || 'unspecified',
    buildId, fontManifest,
    runs: [], rawFontProbes: [] };
  try {
    for (const profile of ['native', 'slow4g-cpu4']) {
      for (const width of [375, 1440]) {
        for (let run = 1; run <= runs; run++) {
          // A new context per navigation: no storage, cookies, HTTP cache or SW.
          const context = await browser.newContext({ viewport: { width, height: 900 },
            deviceScaleFactor: 1, colorScheme: 'light', reducedMotion: 'no-preference',
            serviceWorkers: 'block' });
          const page = await context.newPage();
          const cdp = await context.newCDPSession(page);
          await cdp.send('Network.enable');
          await cdp.send('Network.setCacheDisabled', { cacheDisabled: true });
          if (profile !== 'native') {
            await cdp.send('Network.emulateNetworkConditions', { offline: false, latency: 150,
              downloadThroughput: 1600000 / 8, uploadThroughput: 750000 / 8, connectionType: 'cellular4g' });
            await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 });
          }
          const transfers = new Map(), errors = [], consoleErrors = [], blocked = [], failedRequests = [];
          // Never contact providers or an authenticated backend during public QA.
          await context.route('**/*', route => {
            if (new URL(route.request().url()).origin !== new URL(base).origin) {
              blocked.push(route.request().url());
              return route.abort('blockedbyclient');
            }
            return route.continue();
          });
          page.on('pageerror', error => errors.push(error.message));
          page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
          page.on('requestfailed', request => failedRequests.push({ url: request.url(), error: request.failure() }));
          cdp.on('Network.responseReceived', ({ requestId, type, response }) => {
            transfers.set(requestId, { url: response.url, type, status: response.status,
              fromDiskCache: response.fromDiskCache || false, fromServiceWorker: response.fromServiceWorker || false,
              headers: response.headers, protocol: response.protocol });
          });
          cdp.on('Network.loadingFinished', ({ requestId, encodedDataLength }) => {
            if (transfers.has(requestId)) transfers.get(requestId).cdpEncodedTransferBytes = encodedDataLength;
          });
          await page.addInitScript(() => {
            window.__ux = { supported: PerformanceObserver.supportedEntryTypes,
              lcp: [], shifts: [], started: performance.now() };
            if (window.__ux.supported.includes('largest-contentful-paint')) {
              new PerformanceObserver(list => list.getEntries().forEach(e => window.__ux.lcp.push({
                startTime: e.startTime, size: e.size, tag: e.element?.tagName,
                text: e.element?.textContent?.slice(0, 160), url: e.url,
              }))).observe({ type: 'largest-contentful-paint', buffered: true });
            }
            if (window.__ux.supported.includes('layout-shift')) {
              new PerformanceObserver(list => list.getEntries().forEach(e => window.__ux.shifts.push({
                startTime: e.startTime, value: e.value, hadRecentInput: e.hadRecentInput,
                sources: e.sources?.map(s => ({ tag: s.node?.tagName, previousRect: s.previousRect, currentRect: s.currentRect })),
              }))).observe({ type: 'layout-shift', buffered: true });
            }
          });
          const response = await page.goto(base, { waitUntil: 'load', timeout: 120000 });
          await page.evaluate(() => document.fonts.ready);
          await page.waitForTimeout(windowMs);
          const metrics = await page.evaluate(() => {
            const ux = window.__ux;
            return { ...ux, observedUntilMs: performance.now(),
              observedLcpMs: ux.supported.includes('largest-contentful-paint') ? ux.lcp.at(-1)?.startTime ?? null : null,
              navigation: performance.getEntriesByType('navigation').map(e => e.toJSON()),
              fonts: [...document.fonts].map(f => ({ family: f.family, style: f.style, weight: f.weight, status: f.status })),
              resources: performance.getEntriesByType('resource').map(e => e.toJSON()),
              fontPreloads: [...document.querySelectorAll('link[rel="preload"][as="font"]')].map(e => e.href),
              viewport: { innerWidth, clientWidth: document.documentElement.clientWidth, scrollWidth: document.documentElement.scrollWidth },
            };
          });
          // Pass the actual tested helper to Chromium, not a second copy of it.
          metrics.observedCls = metrics.supported.includes('layout-shift')
            ? await page.evaluate(calculateCls, metrics.shifts) : null;
          const label = `${profile}-${width}-${run}`;
          await page.screenshot({ path: path.join(output, `${label}-top.png`) });
          const allTransfers = [...transfers.values()];
          report.runs.push({ label, profile, width, run, status: response.status(),
            linkHeader: (await response.allHeaders()).link ?? null, metrics, transfers: allTransfers,
            errors, consoleErrors, blocked, failedRequests });
          console.log(JSON.stringify({ label, lcpMs: metrics.observedLcpMs, cls: metrics.observedCls,
            fonts: allTransfers.filter(t => t.type === 'Font').length }));
          fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify(report, null, 2));
          await context.close();
        }
      }
    }
    const urls = [...new Set(report.runs.flatMap(r => r.transfers.filter(t => t.type === 'Font').map(t => t.url)))];
    for (const url of urls) report.rawFontProbes.push(await rawProbe(url));
  } finally {
    fs.writeFileSync(path.join(output, 'report.json'), JSON.stringify(report, null, 2));
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
