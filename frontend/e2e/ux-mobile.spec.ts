import { expect, test, type Page } from "@playwright/test";
import { calculateCls } from "../../scripts/ux_measure/cls.cjs";

const consentKey = "artiproof.cookie-consent";
const tableName = "Current ArtiProof capabilities and limitations";

async function proveClientInteraction(page: Page) {
  // Neither SSR markup nor persisted storage can perform these state changes.
  // Two real clicks exercise React handlers and their rendered results after reload.
  const dark = page.getByRole("radio", { name: "Dark", exact: true });
  const light = page.getByRole("radio", { name: "Light", exact: true });
  await dark.click();
  await expect(dark).toHaveAttribute("aria-checked", "true");
  await expect(page.locator("html")).toHaveClass(/\bdark\b/);
  await light.click();
  await expect(light).toHaveAttribute("aria-checked", "true");
  await expect(page.locator("html")).not.toHaveClass(/\bdark\b/);
}

test("live measurement helper resets exact CLS boundaries in the browser", async ({ page }) => {
  expect(await page.evaluate(calculateCls, [
    { startTime: 0, value: 0.125 }, { startTime: 1000, value: 0.25 },
  ])).toBe(0.25);
  const span = Array.from({ length: 11 }, (_, i) => ({
    startTime: i * 500, value: i === 0 ? 0.125 : i === 10 ? 0.25 : 0,
  }));
  expect(await page.evaluate(calculateCls, span)).toBe(0.25);
});

test("reload guard rejects cookie absence on an SSR-only page", async ({ browser }) => {
  const context = await browser.newContext({ javaScriptEnabled: false, baseURL: test.info().project.use.baseURL });
  try {
    const page = await context.newPage();
    await page.goto("/");
    await page.reload();
    // The old absence assertion passes without any client execution at all.
    await expect(page.getByRole("dialog", { name: "Cookies", exact: true })).toHaveCount(0);
    await expect(page.getByRole("radio", { name: "Dark", exact: true })).toHaveAttribute("aria-checked", "false");
    await expect(proveClientInteraction(page)).rejects.toThrow(/aria-checked/);
  } finally {
    await context.close();
  }
});

for (const width of [375, 1440]) {
  test.describe(`public landing at ${width} CSSpx`, () => {
    test.use({ viewport: { width, height: 812 }, contextOptions: { reducedMotion: "reduce" }, hasTouch: true });

    for (const choice of ["Reject non-essential", "Accept all"] as const) {
      test(`${choice} dismisses and survives reload`, async ({ page }) => {
        await page.goto("/");
        const dialog = page.getByRole("dialog", { name: "Cookies", exact: true });
        await expect(dialog).toBeVisible();
        const button = dialog.getByRole("button", { name: choice, exact: true });
        await expect(button).toBeInViewport({ ratio: 1 });
        await button.tap();
        await expect(dialog).toHaveCount(0);
        const enabled = choice === "Accept all";
        await expect.poll(() => page.evaluate(key => JSON.parse(localStorage.getItem(key)!).consent, consentKey))
          .toEqual({ essential: true, analytics: enabled, marketing: enabled });
        await page.reload();
        await proveClientInteraction(page);
        await expect(dialog).toHaveCount(0);
      });
    }

    test("preferences are keyboard operable without changing default consent", async ({ page }) => {
      await page.goto("/");
      await page.getByRole("button", { name: "Customise", exact: true }).click();
      await expect(page.getByRole("heading", { name: "Cookie preferences" })).toBeFocused();
      await expect(page.getByRole("checkbox", { name: /^Essential/ })).toBeChecked();
      await expect(page.getByRole("checkbox", { name: /^Essential/ })).toBeDisabled();
      const analytics = page.getByRole("checkbox", { name: /^Analytics/ });
      const marketing = page.getByRole("checkbox", { name: /^Marketing/ });
      await expect(analytics).not.toBeChecked();
      await expect(marketing).not.toBeChecked();
      await page.keyboard.press("Tab");
      await expect(analytics).toBeFocused();
      await page.keyboard.press("Space");
      await page.keyboard.press("Tab");
      await expect(marketing).toBeFocused();
      await page.keyboard.press("Tab");
      await expect(page.getByRole("button", { name: "Save preferences" })).toBeFocused();
      await page.keyboard.press("Enter");
      await expect(page.getByRole("dialog", { name: "Cookies", exact: true })).toHaveCount(0);
      expect(await page.evaluate(key => JSON.parse(localStorage.getItem(key)!).consent, consentKey))
        .toEqual({ essential: true, analytics: true, marketing: false });
      await page.reload();
      await proveClientInteraction(page);
      await expect(page.getByRole("dialog", { name: "Cookies", exact: true })).toHaveCount(0);
    });

    test("comparison keeps every limitation reachable", async ({ page }) => {
      await page.goto("/");
      await page.getByRole("button", { name: "Reject non-essential", exact: true }).click();
      const table = page.getByRole("table", { name: tableName });
      const scroller = table.locator("..");
      await expect(table.locator("tbody tr")).toHaveCount(6);
      await expect(table.getByRole("columnheader", { name: "Limitations", exact: true })).toBeVisible();
      await scroller.scrollIntoViewIfNeeded();
      const dimensions = await scroller.evaluate(e => ({ client: e.clientWidth, scroll: e.scrollWidth }));
      if (width === 375) {
        expect(dimensions.scroll).toBeGreaterThan(dimensions.client);
        await page.getByRole("link", { name: "Skip to main content" }).focus();
        for (let tabs = 0; tabs < 40; tabs++) {
          await page.keyboard.press("Tab");
          if (await scroller.evaluate(e => document.activeElement === e)) break;
        }
        await expect(scroller).toBeFocused();
        await page.keyboard.press("ArrowRight");
        await expect.poll(() => scroller.evaluate(e => e.scrollLeft)).toBeGreaterThan(0);
        // Reach the right edge using actual keyboard input, not setting scrollLeft.
        for (let presses = 0; presses < 8; presses++) await page.keyboard.press("ArrowRight");
        await expect.poll(() => scroller.evaluate(e => e.scrollLeft + e.clientWidth))
          .toBeGreaterThanOrEqual(dimensions.scroll - 1);
        await page.keyboard.press("ArrowLeft");
        await expect.poll(() => scroller.evaluate(e => e.scrollLeft))
          .toBeLessThan(dimensions.scroll - dimensions.client);
      } else {
        expect(dimensions.scroll).toBe(dimensions.client);
      }
      for (const limitation of await table.locator("tbody td:last-child").all()) {
        await limitation.scrollIntoViewIfNeeded();
        await expect(limitation).toBeInViewport({ ratio: 1 });
        const cell = (await limitation.boundingBox())!;
        const clip = (await scroller.boundingBox())!;
        expect(cell.x).toBeGreaterThanOrEqual(clip.x - 1);
        expect(cell.x + cell.width).toBeLessThanOrEqual(clip.x + clip.width + 1);
      }
      await expect(table.getByText("Reports summarize the analysis performed. They do not certify a source or researcher.", { exact: true }))
        .toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth))
        .toBeLessThanOrEqual(width);
    });
  });
}

test.describe("cookie readability regressions", () => {
  test.use({ viewport: { width: 375, height: 320 }, contextOptions: { reducedMotion: "reduce" } });

  test("banner explanation is readable against its rendered translucent backdrop", async ({ page }) => {
    await page.goto("/");
    const dialog = page.getByRole("dialog", { name: "Cookies", exact: true });
    await expect(dialog).toBeVisible();
    await page.evaluate(() => document.fonts.ready);
    const paragraph = dialog.locator("p");
    const box = (await paragraph.boundingBox())!;
    const banner = (await dialog.boundingBox())!;
    const screenshot = (await page.screenshot()).toString("base64");
    const ratio = await paragraph.evaluate(async (element, { screenshot, x, y }) => {
      const image = new Image();
      image.src = `data:image/png;base64,${screenshot}`;
      await image.decode();
      const canvas = document.createElement("canvas");
      canvas.width = image.width;
      canvas.height = image.height;
      const ctx = canvas.getContext("2d", { willReadFrequently: true })!;
      ctx.drawImage(image, 0, 0);
      // Sample the adjacent empty banner padding at the same text-line height.
      const background = [...ctx.getImageData(x, y, 1, 1).data];
      ctx.fillStyle = getComputedStyle(element).color;
      ctx.fillRect(0, 0, 1, 1);
      const foreground = [...ctx.getImageData(0, 0, 1, 1).data];
      const luminance = (rgba: number[]) => rgba.slice(0, 3).map(v => v / 255)
        .map(v => v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)
        .reduce((sum, v, i) => sum + v * [0.2126, 0.7152, 0.0722][i], 0);
      const a = luminance(foreground), b = luminance(background);
      return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    }, { screenshot, x: Math.floor(banner.x + banner.width - 8), y: Math.floor(box.y + 8) });
    await test.info().attach("banner-contrast.json", { body: JSON.stringify({ ratio }), contentType: "application/json" });
    expect(ratio).toBeGreaterThanOrEqual(4.5);
  });

  test("short viewport keeps the preferences panel contained and scrollable", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Customise", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "Cookies", exact: true });
    const box = await dialog.boundingBox();
    expect(box).not.toBeNull();
    expect(box!.y).toBeGreaterThanOrEqual(0);
    expect(box!.y + box!.height).toBeLessThanOrEqual(320);
    const scroll = await dialog.evaluate(e => ({ height: e.clientHeight, content: e.scrollHeight, overflow: getComputedStyle(e).overflowY }));
    await test.info().attach("short-viewport.json", { body: JSON.stringify({ box, scroll }), contentType: "application/json" });
    expect(scroll.content).toBeGreaterThan(scroll.height);
    expect(scroll.overflow).toBe("auto");
    await dialog.evaluate(e => { e.scrollTop = 0; });
    await expect(dialog.getByRole("heading", { name: "Cookies", exact: true })).toBeInViewport({ ratio: 1 });
    await expect(dialog.getByRole("link", { name: "privacy policy" })).toBeInViewport({ ratio: 1 });
    await page.getByRole("button", { name: "Save preferences" }).click();
    await expect(dialog).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.style.getPropertyValue("--banner-h"))).toBe("");
  });

  test("preference descriptions have AA small-text contrast on their opaque panel", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: "Customise", exact: true }).click();
    const contrast = await page.getByRole("dialog").locator("label > span > span:last-child").evaluateAll(elements => {
      // Canvas resolves Tailwind's Lab colors into sRGB; do not assume hex tokens.
      const ctx = document.createElement("canvas").getContext("2d", { willReadFrequently: true })!;
      const rgb = (color: string) => {
        ctx.clearRect(0, 0, 1, 1);
        ctx.fillStyle = color;
        ctx.fillRect(0, 0, 1, 1);
        return [...ctx.getImageData(0, 0, 1, 1).data];
      };
      const luminance = (rgba: number[]) => rgba.slice(0, 3).map(v => v / 255)
        .map(v => v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)
        .reduce((sum, v, i) => sum + v * [0.2126, 0.7152, 0.0722][i], 0);
      return elements.map(e => {
        let parent: Element | null = e;
        let background = [0, 0, 0, 0];
        while (parent) {
          background = rgb(getComputedStyle(parent).backgroundColor);
          if (background[3] === 255) break;
          parent = parent.parentElement;
        }
        if (!parent) throw Error("No opaque background to measure");
        const a = luminance(rgb(getComputedStyle(e).color)), b = luminance(background);
        return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
      });
    });
    expect(contrast).toHaveLength(3);
    await test.info().attach("preference-contrast.json", { body: JSON.stringify(contrast), contentType: "application/json" });
    for (const ratio of contrast) expect(ratio).toBeGreaterThanOrEqual(4.5);
  });
});
