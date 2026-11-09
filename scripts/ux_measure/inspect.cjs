const { chromium } = require('../../frontend/node_modules/@playwright/test');
const fs = require('node:fs');
const path = require('node:path');
const output = process.env.UX_OUTPUT;
if (!output || !path.isAbsolute(output)) throw Error('Set absolute UX_OUTPUT');
fs.mkdirSync(output, { recursive: true });
const base = process.env.UX_BASE_URL || 'http://127.0.0.1:3204';
if (new URL(base).hostname !== '127.0.0.1') throw Error('Loopback only');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const report = { browser: browser.version(), widths: [] };
  try {
    for (const width of [375, 1440]) {
      const context = await browser.newContext({ viewport: { width, height: 812 }, reducedMotion: 'reduce' });
      await context.route('**/*', route => new URL(route.request().url()).origin === new URL(base).origin
        ? route.continue() : route.abort());
      const page = await context.newPage();
      await page.goto(base, { waitUntil: 'networkidle' });
      await page.evaluate(() => document.fonts.ready);
      const dialog = page.getByRole('dialog', { name: 'Cookies', exact: true });
      await dialog.waitFor();
      const initial = await dialog.boundingBox();
      await page.screenshot({ path: path.join(output, `${width}-cookie.png`) });
      await page.getByRole('button', { name: 'Customise', exact: true }).click();
      await page.getByRole('heading', { name: 'Cookie preferences' }).waitFor();
      const settings = await dialog.boundingBox();
      const textStyles = await dialog.locator('p, label span').evaluateAll(elements => {
        const ctx = document.createElement('canvas').getContext('2d', { willReadFrequently: true });
        const rgb = color => {
          ctx.clearRect(0, 0, 1, 1); ctx.fillStyle = color; ctx.fillRect(0, 0, 1, 1);
          return [...ctx.getImageData(0, 0, 1, 1).data];
        };
        const luminance = rgba => rgba.slice(0, 3).map(v => v / 255)
          .map(v => v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)
          .reduce((sum, v, i) => sum + v * [0.2126, 0.7152, 0.0722][i], 0);
        return elements.map(e => {
          let ancestor = e, background, translucent = false;
          while (ancestor) {
            background = rgb(getComputedStyle(ancestor).backgroundColor);
            if (background[3] === 255) break;
            if (background[3] > 0) translucent = true;
            ancestor = ancestor.parentElement;
          }
          const style = getComputedStyle(e), foreground = rgb(style.color);
          const a = luminance(foreground), b = luminance(background);
          return { text: e.textContent, color: style.color, background, foreground,
            contrastOnOpaqueAncestor: ancestor && !translucent ? (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05) : null,
            size: style.fontSize, lineHeight: style.lineHeight };
        });
      });
      await page.screenshot({ path: path.join(output, `${width}-settings.png`) });
      let short = null;
      if (width === 375) {
        await page.setViewportSize({ width, height: 320 });
        await page.waitForTimeout(200);
        const box = await dialog.boundingBox();
        const heading = await page.getByRole('heading', { name: 'Cookie preferences' }).boundingBox();
        const scroll = await dialog.evaluate(e => ({ scrollHeight: e.scrollHeight, clientHeight: e.clientHeight,
          overflowY: getComputedStyle(e).overflowY, scrollTop: e.scrollTop }));
        await dialog.hover({ position: { x: 100, y: box.height - 30 } }).catch(() => {});
        await page.mouse.wheel(0, -1000);
        await page.waitForTimeout(200);
        short = { box, heading, scroll, afterWheel: await dialog.evaluate(e => e.scrollTop) };
        await page.screenshot({ path: path.join(output, '375-short-settings.png') });
        await page.setViewportSize({ width, height: 812 });
      }
      await page.getByRole('button', { name: 'Save preferences' }).click();
      const dismissed = await dialog.count() === 0;
      const stored = await page.evaluate(() => JSON.parse(localStorage.getItem('artiproof.cookie-consent')));
      const table = page.getByRole('table', { name: 'Current ArtiProof capabilities and limitations' });
      const scroller = table.locator('..');
      await scroller.scrollIntoViewIfNeeded();
      // Traverse real tab order from a known page anchor, no forced focus on scroller.
      await page.getByRole('link', { name: 'Skip to main content' }).focus();
      let tabs = 0;
      const overflows = await scroller.evaluate(e => e.scrollWidth > e.clientWidth);
      for (; overflows && tabs < 60; tabs++) {
        await page.keyboard.press('Tab');
        if (await scroller.evaluate(e => document.activeElement === e)) break;
      }
      const focused = await scroller.evaluate(e => document.activeElement === e);
      const leftBefore = await scroller.evaluate(e => e.scrollLeft);
      if (focused) {
        await page.keyboard.press('ArrowRight');
        await page.waitForTimeout(250);
      }
      const comparison = await scroller.evaluate(e => ({ clientWidth: e.clientWidth, scrollWidth: e.scrollWidth,
        scrollLeft: e.scrollLeft, tabIndex: e.tabIndex, overflowX: getComputedStyle(e).overflowX,
        pageWidth: document.documentElement.clientWidth, pageScrollWidth: document.documentElement.scrollWidth }));
      // Full content can be reached by horizontal scrolling independently of keyboard.
      await scroller.evaluate(e => { e.scrollLeft = e.scrollWidth; });
      const rightmost = await scroller.evaluate(e => e.scrollLeft);
      await scroller.scrollIntoViewIfNeeded();
      await page.screenshot({ path: path.join(output, `${width}-comparison-right.png`) });
      await page.locator('#compare').screenshot({ path: path.join(output, `${width}-comparison-section.png`) });
      report.widths.push({ width, initial, settings, textStyles, short, dismissed, stored,
        comparison: { ...comparison, focused, tabs, leftBefore, rightmost } });
      await context.close();
    }
  } finally {
    fs.writeFileSync(path.join(output, 'usability.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report, null, 2));
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
