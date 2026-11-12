/// <reference lib="dom" />
// Browser globals are only used inside page.evaluate() callbacks.
import { expect, test } from '@playwright/test';

const FONT = 'Atkinson Hyperlegible';

test('[deployment_rpi.AC-15] offline, the home page is shown with Atkinson Hyperlegible', async ({
  page,
  context,
}) => {
  // First visit online: the service worker installs and precaches the app shell.
  await page.goto('/');
  await page.evaluate(async () => {
    await navigator.serviceWorker.ready;
  });
  // The next load must be controlled by the service worker.
  await page.reload();
  await expect
    .poll(() => page.evaluate(() => navigator.serviceWorker.controller !== null))
    .toBe(true);

  await context.setOffline(true);
  const fonts: { url: string; ok: boolean; fromServiceWorker: boolean }[] = [];
  page.on('response', (response) => {
    if (response.url().endsWith('.woff2')) {
      fonts.push({
        url: response.url(),
        ok: response.ok(),
        fromServiceWorker: response.fromServiceWorker(),
      });
    }
  });
  await page.reload();

  await expect(page.getByRole('main')).toBeVisible();
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  const loaded = await page.evaluate(
    (family) =>
      [...document.fonts]
        .filter((face) => face.family.replace(/["']/g, '') === family)
        .map((face) => ({ weight: face.weight, status: face.status })),
    FONT,
  );
  const used = await page.evaluate(
    () => getComputedStyle(document.querySelector('h1') ?? document.body).fontFamily,
  );

  expect(used).toContain(FONT);
  // The faces the page uses (regular and bold, latin) come from the precache, not the network.
  expect(loaded.filter((face) => face.status === 'loaded').map((face) => face.weight)).toEqual(
    expect.arrayContaining(['400', '700']),
  );
  expect(loaded.some((face) => face.status === 'error')).toBe(false);
  // The woff2 files are in the service worker's precache (the reload alone could be served by
  // the browser's memory cache in some engines).
  const cachedFonts = await page.evaluate(async () => {
    const urls: string[] = [];
    for (const name of await caches.keys()) {
      const cache = await caches.open(name);
      urls.push(...(await cache.keys()).map((request) => request.url));
    }
    return urls.filter((url) => /\.woff2(\?|$)/.test(url));
  });
  expect(cachedFonts.length).toBeGreaterThanOrEqual(2);
  expect(fonts.length).toBeGreaterThan(0);
  for (const font of fonts) {
    expect(font, font.url).toMatchObject({ ok: true, fromServiceWorker: true });
  }
});
