/// <reference lib="dom" />
/// <reference lib="dom.iterable" />
// Browser globals are only used inside page.evaluate() callbacks.
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page, type Route, type TestInfo } from '@playwright/test';
import { fileURLToPath } from 'node:url';

import {
  ARRIVALS_REALTIME,
  LINE_NOT_AT_STOP,
  NETWORK_UNAVAILABLE,
  POSITION_EN_ROUTE,
  POSITION_NO_ARRIVAL,
  POSITION_NOT_STARTED,
  SHAPE_93,
  STOP_508,
} from './fixtures';

const WCAG_21_AA = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];
const TOKEN = 'AbCdEfGhIjKlMnOpQrStUv';
const STOP_URL = `/p/508?t=${TOKEN}`;
const MAP_URL = `/p/508/map/93/0?t=${TOKEN}`;
const APP_ORIGIN = 'http://localhost:4173';
const OSM_TILES = 'tile.openstreetmap.org';
/** 1 × 1 light grey PNG served instead of every map tile (passenger_map_view.AC-14). */
const TILE_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGN49+ETAAWgAtEyI0F/AAAAAElFTkSuQmCC',
  'base64',
);
const DESTINATION = 'Passeig Marítim - Hospital Malva-rosa';

/**
 * Screenshots for the visual review of passenger_map_view.AC-15 (docs/design.md §5.7).
 * Regenerated on every run (Playwright empties test-results/ first; not versioned):
 * frontend/test-results/passenger_map_view/<project>/<name>.png
 */
const CAPTURES_DIR = fileURLToPath(new URL('../test-results/passenger_map_view/', import.meta.url));

const TEXTS = {
  es: {
    title: `Línea 93 hacia ${DESTINATION}`,
    back: 'Volver a la parada',
    summary: 'Dónde está el autobús',
    region: 'Mapa del recorrido',
    estimated: 'Posición estimada',
    yourStop: 'Tu parada',
    bus: 'Estimada',
    zoomIn: 'Acercar',
    zoomOut: 'Alejar',
    attribution: '© colaboradores de OpenStreetMap',
    enRoute:
      'El autobús está a 3,4 km de tu parada, a 3 paradas. Próxima parada: Cid - Hospital General. Llega en 5 minutos.',
  },
  ca: {
    title: `Línia 93 cap a ${DESTINATION}`,
    back: 'Torna a la parada',
    summary: "On està l'autobús",
    region: 'Mapa del recorregut',
    estimated: 'Posició estimada',
    yourStop: 'La teua parada',
    bus: 'Estimada',
    zoomIn: 'Acosta',
    zoomOut: 'Allunya',
    attribution: "© col·laboradors d'OpenStreetMap",
    enRoute:
      "L'autobús està a 3,4 km de la teua parada, a 3 parades. Pròxima parada: Cid - Hospital General. Arriba en 5 minuts.",
  },
} as const;

type Lang = keyof typeof TEXTS;
type Reply = { status: number; body: unknown };

interface Network {
  /** Zoom level of every tile request (all answered locally). */
  tileZooms: number[];
  /** Requests that would have left the machine (other than tiles): must stay empty. */
  external: string[];
  /** API paths without a fixture: must stay empty. */
  unexpected: string[];
}

/**
 * Nothing leaves the browser (passenger_map_view.AC-14): the API is served from e2e/fixtures,
 * every OSM tile is a local PNG and any other origin is aborted and recorded. `replies.position`
 * is read on every request, so a test can change the next refresh.
 */
async function mockNetwork(page: Page, replies: { position: Reply; shape?: Reply }) {
  const network: Network = { tileZooms: [], external: [], unexpected: [] };
  await page.route('**/*', async (route: Route) => {
    const url = new URL(route.request().url());
    if (url.hostname === OSM_TILES) {
      network.tileZooms.push(Number(url.pathname.split('/')[1]));
      await route.fulfill({ status: 200, contentType: 'image/png', body: TILE_PNG });
      return;
    }
    if (url.origin !== APP_ORIGIN) {
      network.external.push(url.href);
      await route.abort();
      return;
    }
    if (!url.pathname.startsWith('/api/v1/')) {
      await route.continue(); // the app itself, from the local preview server
      return;
    }
    let reply: Reply;
    if (url.pathname === '/api/v1/stops/508') reply = { status: 200, body: STOP_508 };
    else if (url.pathname === '/api/v1/stops/508/arrivals')
      reply = { status: 200, body: ARRIVALS_REALTIME };
    else if (url.pathname === '/api/v1/stops/508/lines/93/position') reply = replies.position;
    else if (url.pathname === '/api/v1/shapes/994_488_2271')
      reply = replies.shape ?? { status: 200, body: SHAPE_93 };
    else {
      network.unexpected.push(url.pathname);
      reply = { status: 500, body: {} };
    }
    await route.fulfill({
      status: reply.status,
      contentType: reply.status < 400 ? 'application/json' : 'application/problem+json',
      body: JSON.stringify(reply.body),
    });
  });
  return network;
}

function expectNoNetworkLeaks(network: Network) {
  expect(network.external).toEqual([]);
  expect(network.unexpected).toEqual([]);
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

/** WCAG 2.1 A/AA; only Leaflet's decorative tiles are excluded (AC-14). */
async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(WCAG_21_AA)
    .exclude('.leaflet-tile-pane')
    .analyze();
  expect(results.violations).toEqual([]);
}

function mapRegion(page: Page, lang: Lang) {
  return page.getByRole('region', { name: TEXTS[lang].region });
}

/** The map has been framed and painted: the route and the stops are drawn. */
async function expectMapDrawn(page: Page, lang: Lang) {
  const map = mapRegion(page, lang);
  await expect(map.locator('.leaflet-route-pane path')).toHaveCount(1);
  await expect(map.locator('.leaflet-overlay-pane path')).toHaveCount(SHAPE_93.stops.length);
}

test.use({ serviceWorkers: 'block' });

for (const [lang, locale] of [
  ['es', 'es-ES'],
  ['ca', 'ca-ES'],
] as const) {
  test.describe(`map view in ${lang}`, () => {
    test.use({ locale });
    const texts = TEXTS[lang];

    test(`[passenger_map_view.AC-07] [passenger_map_view.AC-09] [passenger_map_view.AC-11] [passenger_map_view.AC-14] [passenger_map_view.AC-15] EN_ROUTE with no WCAG 2.1 A/AA violations (${lang})`, async ({
      page,
    }, testInfo) => {
      const network = await mockNetwork(page, {
        position: { status: 200, body: POSITION_EN_ROUTE },
      });
      await page.goto(MAP_URL);

      await expect(page.getByRole('heading', { level: 1 })).toHaveText(texts.title);
      await expect(page).toHaveTitle(`${texts.title} · AvisaBus`);
      await expect(page.getByRole('link', { name: texts.back })).toHaveAttribute('href', STOP_URL);
      const summary = page.getByRole('region', { name: texts.summary });
      await expect(summary).toContainText(texts.enRoute);
      await expect(summary.getByText(texts.estimated)).toBeVisible();

      const map = mapRegion(page, lang);
      await expect(map).toBeVisible();
      await expectMapDrawn(page, lang);
      await expect(map.locator('.leaflet-route-pane path')).toHaveAttribute('stroke', '#e50000');
      await expect(map.getByText(texts.yourStop, { exact: true })).toBeVisible();
      await expect(map.getByText(texts.bus, { exact: true })).toBeVisible();
      await expect(map.locator('[data-bus-arrow]')).toHaveAttribute('style', /rotate\(90\.9deg\)/);

      const attribution = map.getByRole('link', { name: texts.attribution });
      await expect(attribution).toBeVisible();
      await expect(attribution).toHaveAttribute('href', 'https://www.openstreetmap.org/copyright');
      for (const name of [texts.zoomIn, texts.zoomOut]) {
        const box = await map.getByRole('button', { name }).boundingBox();
        expect(box?.width).toBeGreaterThanOrEqual(44);
        expect(box?.height).toBeGreaterThanOrEqual(44);
      }
      // The map box of docs/design.md §5.7: 360 px high.
      expect((await map.boundingBox())?.height).toBeCloseTo(360, 0);

      await expectNoAxeViolations(page);
      expect(network.tileZooms.length).toBeGreaterThan(0);
      expectNoNetworkLeaks(network);
      await capture(page, testInfo, `map-en-route-${lang}`);
    });
  });
}

test.describe('map view states', () => {
  test.use({ locale: 'es-ES' });

  test('[passenger_map_view.AC-04] [passenger_map_view.AC-05] [passenger_map_view.AC-14] [passenger_map_view.AC-15] NOT_STARTED with the timetable, with no WCAG 2.1 A/AA violations', async ({
    page,
  }, testInfo) => {
    const network = await mockNetwork(page, {
      position: { status: 200, body: POSITION_NOT_STARTED },
    });
    await page.goto(MAP_URL);

    const summary = page.getByRole('region', { name: 'Dónde está el autobús' });
    await expect(summary).toContainText(
      'El autobús aún no ha salido de Avinguda del Cid. Llega a las 08:58.',
    );
    await expect(summary.getByText('Posición según horario')).toBeVisible();
    await expectMapDrawn(page, 'es');
    await expect(mapRegion(page, 'es').getByText('Según horario', { exact: true })).toBeVisible();

    await expectNoAxeViolations(page);
    expectNoNetworkLeaks(network);
    await capture(page, testInfo, 'map-not-started-es');
  });

  test('[passenger_map_view.AC-04] [passenger_map_view.AC-07] [passenger_map_view.AC-14] [passenger_map_view.AC-15] NO_ARRIVAL: only the route and the stops, with no WCAG 2.1 A/AA violations', async ({
    page,
  }, testInfo) => {
    const network = await mockNetwork(page, {
      position: { status: 200, body: POSITION_NO_ARRIVAL },
    });
    await page.goto(MAP_URL);

    await expect(page.getByRole('region', { name: 'Dónde está el autobús' })).toContainText(
      'Posición no disponible en este momento. No hay llegadas previstas de esta línea en tu parada.',
    );
    await expectMapDrawn(page, 'es');
    const map = mapRegion(page, 'es');
    await expect(map.getByText('Tu parada', { exact: true })).toBeVisible();
    await expect(map.locator('.leaflet-marker-pane > *')).toHaveCount(0);

    await expectNoAxeViolations(page);
    expectNoNetworkLeaks(network);
    await capture(page, testInfo, 'map-no-arrival-es');
  });

  test('[passenger_map_view.AC-13] [passenger_map_view.AC-15] a line that does not stop here, with no WCAG 2.1 A/AA violations', async ({
    page,
  }, testInfo) => {
    const network = await mockNetwork(page, {
      position: { status: 404, body: LINE_NOT_AT_STOP },
    });
    await page.goto(MAP_URL);

    await expect(page.getByRole('heading', { level: 1 })).toHaveText(
      'No se encuentra esta línea en tu parada',
    );
    await expect(page.getByRole('link', { name: 'Volver a la parada' })).toHaveAttribute(
      'href',
      STOP_URL,
    );
    await expectNoAxeViolations(page);
    expectNoNetworkLeaks(network);
    await capture(page, testInfo, 'map-line-not-found-es');
  });

  test('[passenger_map_view.AC-13] [passenger_map_view.AC-15] the API fails: "Reintentar", with no WCAG 2.1 A/AA violations', async ({
    page,
  }, testInfo) => {
    const replies = { position: { status: 503, body: NETWORK_UNAVAILABLE } as Reply };
    const network = await mockNetwork(page, replies);
    await page.goto(MAP_URL);

    const retry = page.getByRole('button', { name: 'Reintentar' });
    await expect(retry).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText('No se han podido cargar los datos.')).toBeVisible();
    await expectNoAxeViolations(page);
    await capture(page, testInfo, 'map-error-es');

    replies.position = { status: 200, body: POSITION_EN_ROUTE };
    await retry.click();
    await expect(retry).toHaveCount(0);
    await expectMapDrawn(page, 'es');
    expectNoNetworkLeaks(network);
  });

  test('[passenger_map_view.AC-01] [passenger_map_view.AC-02] [passenger_map_view.AC-03] opens from the stop view, shows "Cargando mapa…" and goes back', async ({
    page,
  }) => {
    const network = await mockNetwork(page, {
      position: { status: 200, body: POSITION_EN_ROUTE },
    });
    // Hold the map chunk to see the fallback while it loads.
    let releaseChunk!: () => void;
    const chunkHeld = new Promise<void>((resolve) => (releaseChunk = resolve));
    let chunkRequested = false;
    await page.route(/\/assets\/MapPage-[\w-]+\.js$/, async (route) => {
      chunkRequested = true;
      await chunkHeld;
      await route.continue();
    });
    await page.goto(STOP_URL);

    const link = page.getByRole('link', {
      name: `Ver en el mapa la línea 93 hacia ${DESTINATION}`,
    });
    await expect(link).toHaveCount(2); // the two 93 arrivals; not the 70 without direction nor N4
    await link.first().click();

    const loading = page.getByRole('status').filter({ hasText: 'Cargando mapa…' });
    await expect(loading).toBeVisible();
    expect(chunkRequested).toBe(true);
    releaseChunk();

    await expect(page).toHaveURL(MAP_URL);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText(TEXTS.es.title);
    await expect(page.getByRole('heading', { level: 1 })).toBeFocused();
    await expectMapDrawn(page, 'es');

    await page.getByRole('link', { name: 'Volver a la parada' }).click();
    await expect(page).toHaveURL(STOP_URL);
    await expect(page.getByRole('heading', { level: 1 })).toHaveText("Parc de l'Oest - Enguera");
    expectNoNetworkLeaks(network);
  });

  test('[passenger_map_view.AC-09] the map works with the keyboard: arrows pan, +/- and the buttons zoom', async ({
    page,
  }, testInfo) => {
    const network = await mockNetwork(page, {
      position: { status: 200, body: POSITION_EN_ROUTE },
    });
    await page.goto(MAP_URL);
    await expectMapDrawn(page, 'es');
    const map = mapRegion(page, 'es');
    const container = map.locator('.leaflet-container');
    const pane = map.locator('.leaflet-map-pane');
    /** Zoom levels of the tiles on the map (old levels go away once a zoom ends). */
    const zooms = () =>
      page.evaluate(() => [
        ...new Set(
          [...document.querySelectorAll<HTMLImageElement>('.leaflet-tile-pane img')].map((img) =>
            Number(new URL(img.src).pathname.split('/')[1]),
          ),
        ),
      ]);

    await container.focus();
    await expect(container).toBeFocused();
    // Visible focus on the map box (Leaflet's panes would cover a ring on the map itself).
    await expect(map).toHaveCSS('outline-style', 'solid');
    await expect(map).toHaveCSS('outline-width', '3px');
    await capture(page, testInfo, 'map-focused-es');
    const before = await pane.getAttribute('style');
    await page.keyboard.press('ArrowRight');
    await expect.poll(() => pane.getAttribute('style')).not.toBe(before);

    await expect.poll(async () => (await zooms()).length).toBe(1);
    const [zoom = 0] = await zooms();
    await page.keyboard.press('+');
    await expect.poll(zooms).toEqual([zoom + 1]);
    await page.keyboard.press('-');
    await expect.poll(zooms).toEqual([zoom]);

    const zoomIn = map.getByRole('button', { name: 'Acercar' });
    await zoomIn.focus();
    await capture(page, testInfo, 'map-zoom-focused-es');
    await page.keyboard.press('Enter');
    await expect.poll(zooms).toEqual([zoom + 1]);
    await map.getByRole('button', { name: 'Alejar' }).click();
    await expect.poll(zooms).toEqual([zoom]);
    expectNoNetworkLeaks(network);
  });
});

test.describe('map view with reduced motion', () => {
  test.use({ locale: 'es-ES', reducedMotion: 'reduce' });

  test('[passenger_map_view.AC-10] the arrow keys and the zoom move the map without animation', async ({
    page,
  }) => {
    const network = await mockNetwork(page, {
      position: { status: 200, body: POSITION_EN_ROUTE },
    });
    await page.goto(MAP_URL);
    await expectMapDrawn(page, 'es');
    const map = mapRegion(page, 'es');
    const pane = map.locator('.leaflet-map-pane');
    // Records every animation class Leaflet puts on the map pane from now on.
    await page.evaluate(() => {
      const target = document.querySelector('.leaflet-map-pane')!;
      const seen: string[] = [];
      (window as unknown as { animations: string[] }).animations = seen;
      new MutationObserver(() => {
        for (const name of ['leaflet-pan-anim', 'leaflet-zoom-anim']) {
          if (target.classList.contains(name) || target.parentElement?.classList.contains(name))
            seen.push(name);
        }
      }).observe(target.parentElement!, {
        attributes: true,
        subtree: true,
        attributeFilter: ['class'],
      });
    });

    await map.locator('.leaflet-container').focus();
    const before = await pane.getAttribute('style');
    await page.keyboard.press('ArrowRight');
    // The pane jumps to its new position in the same task as the key press.
    expect(await pane.getAttribute('style')).not.toBe(before);
    await page.keyboard.press('+');
    await map.getByRole('button', { name: 'Alejar' }).click();
    await page.waitForTimeout(400); // longer than Leaflet's 0.25 s animations

    expect(
      await page.evaluate(() => (window as unknown as { animations: string[] }).animations),
    ).toEqual([]);
    expectNoNetworkLeaks(network);
  });
});
