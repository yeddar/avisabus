/// <reference lib="dom" />
/// <reference lib="dom.iterable" />
// Browser globals are only used inside page.evaluate() callbacks.
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page, type TestInfo } from '@playwright/test';
import { fileURLToPath } from 'node:url';

import {
  ARRIVALS_EMPTY,
  ARRIVALS_REALTIME,
  ARRIVALS_SCHEDULED,
  NETWORK_UNAVAILABLE,
  NOT_FOUND,
  STOP_508,
} from './fixtures';

const WCAG_21_AA = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];
const TOKEN = 'AbCdEfGhIjKlMnOpQrStUv';
const STOP_URL = `/p/508?t=${TOKEN}`;
const UNKNOWN_STOP_URL = `/p/999?t=${TOKEN}`;

/**
 * Screenshots for the visual review of passenger_stop_view.AC-23 (docs/design.md §3–§5).
 * Regenerated on every run (Playwright empties test-results/ first; not versioned):
 * frontend/test-results/passenger_stop_view/<project>/<name>.png
 */
const CAPTURES_DIR = fileURLToPath(
  new URL('../test-results/passenger_stop_view/', import.meta.url),
);

const TEXTS = {
  es: {
    title: "Parc de l'Oest - Enguera · AvisaBus",
    code: 'Parada 508',
    lines: 'Líneas',
    arrivals: 'Próximas llegadas',
    arriving: 'Llegando',
    updated: 'Actualizado a las 08:40:00',
    refresh: 'Actualizar',
    scheduled: 'Sin datos en tiempo real: se muestra el horario programado',
    scheduledSuffix: 'programado',
    empty: 'No hay llegadas previstas en este momento',
    notFound: 'Parada no encontrada',
    notFoundTitle: 'Parada no encontrada · AvisaBus',
    rescan: /Vuelve a escanear el código QR de la parada/,
    attribution: 'Datos: EMT València (GTFS y tiempos de llegada) · Ajuntament de València',
  },
  ca: {
    title: "Parc de l'Oest - Enguera · AvisaBus",
    code: 'Parada 508',
    lines: 'Línies',
    arrivals: 'Pròximes arribades',
    arriving: 'Arribant',
    updated: 'Actualitzat a les 08:40:00',
    refresh: 'Actualitza',
    scheduled: "Sense dades en temps real: es mostra l'horari programat",
    scheduledSuffix: 'programat',
    empty: 'No hi ha arribades previstes en este moment',
    notFound: 'Parada no trobada',
    notFoundTitle: 'Parada no trobada · AvisaBus',
    rescan: /Torna a escanejar el codi QR de la parada/,
    attribution: "Dades: EMT València (GTFS i temps d'arribada) · Ajuntament de València",
  },
} as const;

type Lang = keyof typeof TEXTS;
type Reply = { status: number; body: unknown };

/**
 * Serves the API from e2e/fixtures: nothing leaves the browser. `arrivals` is read on every
 * request, so a test can change the answer of the next refresh.
 */
async function mockApi(page: Page, arrivals: { reply: Reply }) {
  const unexpected: string[] = [];
  await page.route('**/api/v1/**', async (route) => {
    const url = new URL(route.request().url());
    let reply: Reply;
    if (url.pathname === '/api/v1/stops/508') reply = { status: 200, body: STOP_508 };
    else if (url.pathname === '/api/v1/stops/508/arrivals') reply = arrivals.reply;
    else if (url.pathname.startsWith('/api/v1/stops/999')) reply = { status: 404, body: NOT_FOUND };
    else {
      unexpected.push(url.pathname);
      reply = { status: 500, body: {} };
    }
    await route.fulfill({
      status: reply.status,
      contentType: reply.status < 400 ? 'application/json' : 'application/problem+json',
      body: JSON.stringify(reply.body),
    });
  });
  return unexpected;
}

async function capture(page: Page, testInfo: TestInfo, name: string) {
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({
    path: `${CAPTURES_DIR}${testInfo.project.name}/${name}.png`,
    fullPage: true,
    animations: 'disabled',
    caret: 'hide',
  });
}

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_21_AA).analyze();
  expect(results.violations).toEqual([]);
}

function arrivalsSection(page: Page, lang: Lang) {
  return page.getByRole('region', { name: TEXTS[lang].arrivals });
}

test.use({ serviceWorkers: 'block' });

for (const [lang, locale] of [
  ['es', 'es-ES'],
  ['ca', 'ca-ES'],
] as const) {
  test.describe(`stop view in ${lang}`, () => {
    test.use({ locale });
    const texts = TEXTS[lang];

    test(`[passenger_stop_view.AC-04] [passenger_stop_view.AC-22] [passenger_stop_view.AC-23] real-time arrivals with no WCAG 2.1 A/AA violations (${lang})`, async ({
      page,
    }, testInfo) => {
      const unexpected = await mockApi(page, {
        reply: { status: 200, body: ARRIVALS_REALTIME },
      });
      await page.goto(STOP_URL);

      await expect(page.getByRole('heading', { level: 1 })).toHaveText("Parc de l'Oest - Enguera");
      await expect(page).toHaveTitle(texts.title);
      await expect(page.getByRole('main').getByText(texts.code, { exact: true })).toBeVisible();
      const lines = page.getByRole('region', { name: texts.lines }).getByRole('listitem');
      await expect(lines).toHaveCount(2);
      const items = arrivalsSection(page, lang).getByRole('listitem');
      await expect(items).toHaveCount(5);
      await expect(items.nth(0)).toContainText(texts.arriving);
      await expect(items.nth(1)).toContainText('4 min');
      await expect(items.nth(1)).toContainText('Pass. Marítim');
      await expect(page.getByText(texts.updated)).toBeVisible();
      await expect(page.getByRole('contentinfo').getByText(texts.attribution)).toBeVisible();

      const refresh = page.getByRole('button', { name: texts.refresh });
      const box = await refresh.boundingBox();
      expect(box?.height).toBeGreaterThanOrEqual(44);
      expect(box?.width).toBeGreaterThanOrEqual(44);

      await expectNoAxeViolations(page);
      expect(unexpected).toEqual([]);
      await capture(page, testInfo, `stop-realtime-${lang}`);
      await refresh.focus();
      await capture(page, testInfo, `stop-realtime-${lang}-refresh-focused`);
    });

    test(`[passenger_stop_view.AC-22] [passenger_stop_view.AC-23] scheduled timetable with no WCAG 2.1 A/AA violations (${lang})`, async ({
      page,
    }, testInfo) => {
      await mockApi(page, { reply: { status: 200, body: ARRIVALS_SCHEDULED } });
      await page.goto(STOP_URL);

      await expect(page.getByRole('status').filter({ hasText: texts.scheduled })).toBeVisible();
      const items = arrivalsSection(page, lang).getByRole('listitem');
      await expect(items).toHaveCount(2);
      await expect(items.nth(0)).toContainText('08:52');
      await expect(items.nth(0)).toContainText(texts.scheduledSuffix);

      await expectNoAxeViolations(page);
      await capture(page, testInfo, `stop-scheduled-${lang}`);
    });

    test(`[passenger_stop_view.AC-22] [passenger_stop_view.AC-23] no arrivals with no WCAG 2.1 A/AA violations (${lang})`, async ({
      page,
    }, testInfo) => {
      await mockApi(page, { reply: { status: 200, body: ARRIVALS_EMPTY } });
      await page.goto(STOP_URL);

      await expect(arrivalsSection(page, lang).getByText(texts.empty)).toBeVisible();
      await expect(arrivalsSection(page, lang).getByRole('listitem')).toHaveCount(0);

      await expectNoAxeViolations(page);
      await capture(page, testInfo, `stop-empty-${lang}`);
    });

    test(`[passenger_stop_view.AC-16] [passenger_stop_view.AC-22] [passenger_stop_view.AC-23] unknown stop with no WCAG 2.1 A/AA violations (${lang})`, async ({
      page,
    }, testInfo) => {
      await mockApi(page, { reply: { status: 404, body: NOT_FOUND } });
      await page.goto(UNKNOWN_STOP_URL);

      await expect(page.getByRole('heading', { level: 1 })).toHaveText(texts.notFound);
      await expect(page).toHaveTitle(texts.notFoundTitle);
      await expect(page.getByText(texts.rescan)).toBeVisible();
      const main = page.getByRole('main');
      await expect(main).not.toContainText('999');
      await expect(main).not.toContainText(TOKEN);

      await expectNoAxeViolations(page);
      await capture(page, testInfo, `stop-not-found-${lang}`);
    });
  });
}

test.describe('stop view status notices', () => {
  test.use({ locale: 'es-ES' });

  test('[passenger_stop_view.AC-17] [passenger_stop_view.AC-23] keeps the data marked as outdated when the API fails', async ({
    page,
  }, testInfo) => {
    const arrivals = { reply: { status: 200, body: ARRIVALS_REALTIME } as Reply };
    await mockApi(page, arrivals);
    await page.goto(STOP_URL);
    await expect(arrivalsSection(page, 'es').getByRole('listitem')).toHaveCount(5);

    arrivals.reply = { status: 503, body: NETWORK_UNAVAILABLE };
    await page.getByRole('button', { name: 'Actualizar' }).click();

    await expect(page.getByText('Datos de las 08:40, pueden no estar actualizados')).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.getByRole('button', { name: 'Reintentar' })).toBeVisible();
    await expect(arrivalsSection(page, 'es').getByRole('listitem')).toHaveCount(5);
    await expectNoAxeViolations(page);
    await capture(page, testInfo, 'stop-error-stale-es');

    arrivals.reply = { status: 200, body: ARRIVALS_REALTIME };
    await page.getByRole('button', { name: 'Reintentar' }).click();
    await expect(page.getByText('Actualizado a las 08:40:00')).toBeVisible();
  });

  test('[passenger_stop_view.AC-18] [passenger_stop_view.AC-23] shows "Sin conexión" while the browser is offline', async ({
    page,
    context,
  }, testInfo) => {
    await mockApi(page, { reply: { status: 200, body: ARRIVALS_REALTIME } });
    await page.goto(STOP_URL);
    await expect(arrivalsSection(page, 'es').getByRole('listitem')).toHaveCount(5);

    await context.setOffline(true);
    const notice = page.getByRole('status').filter({ hasText: 'Sin conexión.' });
    await expect(notice).toBeVisible();
    await expectNoAxeViolations(page);
    await capture(page, testInfo, 'stop-offline-es');

    await context.setOffline(false);
    await expect(notice).toHaveCount(0);
  });

  test('[passenger_stop_view.AC-19] [passenger_stop_view.AC-23] the home page offers the last stop opened', async ({
    page,
  }, testInfo) => {
    await mockApi(page, { reply: { status: 200, body: ARRIVALS_REALTIME } });
    await page.goto(STOP_URL);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText("Parc de l'Oest - Enguera");

    await page.goto('/');
    const link = page.getByRole('link', { name: "Tu última parada: Parc de l'Oest - Enguera" });
    await expect(link).toBeVisible();
    await expectNoAxeViolations(page);
    await capture(page, testInfo, 'home-last-stop-es');

    await link.click();
    await expect(page).toHaveURL(STOP_URL);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText("Parc de l'Oest - Enguera");
  });

  test('[passenger_stop_view.AC-20] [passenger_stop_view.AC-23] unknown routes show "Página no encontrada"', async ({
    page,
  }, testInfo) => {
    await page.goto('/no-existe');

    await expect(page.getByRole('heading', { level: 1 })).toHaveText('Página no encontrada');
    await expect(page.getByRole('link', { name: 'Ir a la portada' })).toHaveAttribute('href', '/');
    await expectNoAxeViolations(page);
    await capture(page, testInfo, 'not-found-es');
  });
});
