/// <reference lib="dom" />
// Browser globals are only used inside page.evaluate() callbacks.
import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page, type TestInfo, type WebSocketRoute } from '@playwright/test';
import { fileURLToPath } from 'node:url';

import type { DriverView } from '../src/features/driver/types';
import { DRIVER_DEPARTURES, DRIVER_LINES, DRIVER_VIEW } from './fixtures/driver';

const WCAG_21_AA = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];
const APP_ORIGIN = 'http://localhost:4173';
const TABLET = 'tablet-landscape';
const TOKEN = 'driver-token-e2e';
const CODE = '12345678';
const HEADSIGN = 'Passeig Marítim - Hospital Malva-rosa';
const POSITION = { latitude: 39.4699, longitude: -0.3763, accuracy: 12 };

/**
 * Screenshots for the visual review of driver_ui.AC-12 (docs/design.md §5.9). Regenerated on every
 * run (Playwright empties test-results/ first; not versioned):
 * frontend/test-results/driver_ui/<project>/<name>-<lang>.png
 */
const CAPTURES_DIR = fileURLToPath(new URL('../test-results/driver_ui/', import.meta.url));

const TEXTS = {
  es: {
    code: 'Código de acceso',
    enter: 'Entrar',
    invalid: 'Código no válido',
    line: 'Línea 93',
    pickDeparture: 'Elige la salida',
    taken: 'Ya en servicio',
    departure: 'Salida a las 08:40',
    none: 'Sin solicitudes en las próximas paradas',
    isNew: 'Nueva',
    waitingNew: '2 personas esperando',
    ramp: '1 rampa',
    seat: '1 asiento',
    capacity: 'Esperan 35 personas y quedan 30 plazas',
    seats: 'Piden asiento 5 personas y quedan 2 asientos',
    places: '30 plazas libres · 4 asientos',
    stale: 'Posición desactualizada',
    finished: 'Fin del recorrido',
    nextDeparture: 'Elegir la siguiente salida',
    end: 'Finalizar turno',
    confirm: '¿Finalizar el turno?',
    yes: 'Finalizar',
    ended: 'Turno finalizado',
  },
  ca: {
    code: "Codi d'accés",
    enter: 'Entra',
    invalid: 'Codi no vàlid',
    line: 'Línia 93',
    pickDeparture: "Tria l'eixida",
    taken: 'Ja en servei',
    departure: 'Eixida a les 08:40',
    none: 'Sense sol·licituds en les pròximes parades',
    isNew: 'Nova',
    waitingNew: '2 persones esperant',
    ramp: '1 rampa',
    seat: '1 seient',
    capacity: 'Esperen 35 persones i queden 30 places',
    seats: 'Demanen seient 5 persones i queden 2 seients',
    places: '30 places lliures · 4 seients',
    stale: 'Posició desactualitzada',
    finished: 'Fi del recorregut',
    nextDeparture: 'Tria la següent eixida',
    end: 'Finalitza el torn',
    confirm: 'Vols finalitzar el torn?',
    yes: 'Finalitza',
    ended: 'Torn finalitzat',
  },
} as const;

type Lang = keyof typeof TEXTS;

interface DriverBackend {
  socket: WebSocketRoute | null;
  helloToken: string | null;
  serviceBodies: unknown[];
  positions: { lat: number; lon: number }[];
  deletes: number;
  unexpected: string[];
}

function requestView(): DriverView {
  const [first, ...rest] = DRIVER_VIEW.stops;
  if (first === undefined) throw new Error('the view fixture has no stops');
  return {
    ...DRIVER_VIEW,
    generated_at: '2026-11-09T07:42:00Z',
    stops: [
      {
        ...first,
        waiting: 2,
        needs: { RAMP: 1, EXTRA_TIME: 0, SEAT: 1, VISUAL: 0 },
        alert_ids: ['alert-1', 'alert-2'],
      },
      ...rest,
    ],
    total_waiting: 2,
  };
}

function capacityView(): DriverView {
  const [first, ...rest] = requestView().stops;
  if (first === undefined) throw new Error('the view fixture has no stops');
  return {
    ...requestView(),
    generated_at: '2026-11-09T07:43:00Z',
    stops: [
      {
        ...first,
        waiting: 35,
        needs: { RAMP: 1, EXTRA_TIME: 0, SEAT: 5, VISUAL: 0 },
      },
      ...rest,
    ],
    total_waiting: 35,
    free_places: 30,
    free_seats: 2,
    capacity_alert: true,
    seat_alert: true,
  };
}

/** Simulated /api/v1/driver and /ws/driver: nothing leaves the browser. */
async function mockDriver(page: Page): Promise<DriverBackend> {
  const backend: DriverBackend = {
    socket: null,
    helloToken: null,
    serviceBodies: [],
    positions: [],
    deletes: 0,
    unexpected: [],
  };
  let selected = false;

  await page.routeWebSocket('**/ws/driver', (ws) => {
    backend.socket = ws;
    ws.onMessage((frame) => {
      const message = JSON.parse(String(frame)) as { type: string; session_token?: string };
      if (message.type !== 'hello') return;
      backend.helloToken = message.session_token ?? null;
      ws.send(JSON.stringify({ type: 'driver.view', ...DRIVER_VIEW }));
    });
  });

  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const { pathname } = new URL(request.url());
    const method = request.method();
    const authorized = request.headers().authorization === `Bearer ${TOKEN}`;
    let status = 200;
    let body: unknown = null;

    if (pathname === '/api/v1/driver/sessions' && method === 'POST') {
      const { code } = request.postDataJSON() as { code: string };
      if (code === CODE) {
        status = 201;
        body = { session_id: 'session-1', session_token: TOKEN, idle_timeout_s: 600 };
      } else {
        status = 401;
      }
    } else if (!authorized) {
      status = 401;
    } else if (pathname === '/api/v1/driver/sessions/current/view') {
      body = selected ? DRIVER_VIEW : { ...DRIVER_VIEW, service: null, stops: [] };
    } else if (pathname === '/api/v1/driver/lines') {
      body = DRIVER_LINES;
    } else if (pathname === '/api/v1/driver/departures') {
      body = DRIVER_DEPARTURES;
    } else if (pathname === '/api/v1/driver/sessions/current/service' && method === 'PUT') {
      backend.serviceBodies.push(request.postDataJSON());
      selected = true;
      body = {};
    } else if (pathname === '/api/v1/driver/sessions/current/position' && method === 'PUT') {
      const { lat, lon } = request.postDataJSON() as { lat: number; lon: number };
      backend.positions.push({ lat, lon });
      status = 204;
    } else if (pathname === '/api/v1/driver/sessions/current' && method === 'DELETE') {
      backend.deletes += 1;
      status = 204;
    } else {
      backend.unexpected.push(`${method} ${pathname}`);
      status = 500;
    }

    await route.fulfill({
      status,
      contentType: status < 400 ? 'application/json' : 'application/problem+json',
      body: body === null ? '' : JSON.stringify(body),
    });
  });

  return backend;
}

function sendView(backend: DriverBackend, view: DriverView) {
  backend.socket?.send(JSON.stringify({ type: 'driver.view', ...view }));
}

async function capture(page: Page, testInfo: TestInfo, name: string, lang: Lang) {
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({
    path: `${CAPTURES_DIR}${testInfo.project.name}/${name}-${lang}.png`,
    fullPage: true,
    animations: 'disabled',
    caret: 'hide',
  });
}

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_21_AA).analyze();
  expect(results.violations).toEqual([]);
}

test.use({ serviceWorkers: 'block' });

for (const [lang, locale] of [
  ['es', 'es-ES'],
  ['ca', 'ca-ES'],
] as const) {
  test.describe(`driver view in ${lang}`, () => {
    test.use({ locale });
    const texts = TEXTS[lang];

    test.beforeEach(async ({ context }, testInfo) => {
      test.skip(testInfo.project.name !== TABLET, 'the driver view runs on the landscape tablet');
      await context.grantPermissions(['geolocation']);
      await context.setGeolocation(POSITION);
    });

    test(`[driver_ui.AC-11] [driver_ui.AC-12] full flow: code, departure, demand, new request, capacity alert and end (${lang})`, async ({
      page,
    }, testInfo) => {
      const backend = await mockDriver(page);
      const external: string[] = [];
      page.on('request', (request) => {
        if (new URL(request.url()).origin !== APP_ORIGIN) external.push(request.url());
      });

      // Access code.
      await page.goto('/driver');
      const code = page.getByLabel(texts.code);
      await expect(code).toHaveAttribute('inputmode', 'numeric');
      await code.fill(CODE);
      await expect(code).toHaveValue('1234 5678');
      await expectNoAxeViolations(page);
      await capture(page, testInfo, 'acceso', lang);
      await page.getByRole('button', { name: texts.enter, exact: true }).click();

      // Line, direction and departure.
      await page.getByRole('button', { name: texts.line }).click();
      await page.getByRole('button', { name: HEADSIGN }).click();
      await expect(page.getByRole('heading', { level: 1 })).toHaveText(texts.pickDeparture);
      await expect(page.getByRole('button', { name: /08:55/ })).toBeDisabled();
      await expect(page.getByRole('button', { name: /08:55/ })).toContainText(texts.taken);
      await expectNoAxeViolations(page);
      await capture(page, testInfo, 'eleccion-salida', lang);
      await page.getByRole('button', { name: /08:40/ }).click();

      // Demand view without requests.
      await expect(page.getByText(texts.departure)).toBeVisible();
      await expect(page.getByText(texts.none)).toBeVisible();
      await expect(page.getByText(texts.places)).toBeVisible();
      expect(backend.serviceBodies).toEqual([
        { line: '93', direction_id: 0, trip_id: '12345', service_date: '2026-11-09' },
      ]);
      await expect.poll(() => backend.helloToken).toBe(TOKEN);
      const muteIcon = await page.locator('main button svg').first().boundingBox();
      expect(muteIcon?.width).toBe(18);
      await expectNoAxeViolations(page);
      await capture(page, testInfo, 'sin-solicitudes', lang);

      // A new request: highlighted stop with the "Nueva" label.
      sendView(backend, requestView());
      await expect(page.getByText(texts.isNew, { exact: true })).toBeVisible();
      const card = page.getByRole('listitem').filter({ hasText: texts.isNew });
      await expect(card).toContainText(texts.waitingNew);
      await expect(card).toContainText(texts.ramp);
      await expect(card).toContainText(texts.seat);
      await expectNoAxeViolations(page);
      await capture(page, testInfo, 'solicitud-nueva', lang);

      // Capacity and seat strips, announced once.
      sendView(backend, capacityView());
      await expect(page.getByRole('main').getByText(texts.capacity, { exact: true })).toBeVisible();
      await expect(page.getByRole('main').getByText(texts.seats, { exact: true })).toBeVisible();
      await expect(page.getByRole('alert')).toContainText(texts.capacity);
      await expectNoAxeViolations(page);
      await capture(page, testInfo, 'alerta-capacidad', lang);

      // The position reaches the API.
      await expect
        .poll(() => backend.positions.length, { timeout: 15_000 })
        .toBeGreaterThanOrEqual(1);
      expect(backend.positions[0]).toEqual({ lat: POSITION.latitude, lon: POSITION.longitude });

      // GPS out of date, keeping the list.
      sendView(backend, {
        ...capacityView(),
        generated_at: '2026-11-09T07:44:00Z',
        gps: 'STALE',
      });
      await expect(page.getByText(texts.stale)).toBeVisible();
      await expect(card).toContainText(texts.ramp);
      await capture(page, testInfo, 'gps-desactualizado', lang);

      // End of the route.
      sendView(backend, {
        ...DRIVER_VIEW,
        generated_at: '2026-11-09T07:45:00Z',
        finished: true,
        stops: [],
        total_waiting: 0,
      });
      await expect(page.getByText(texts.finished)).toBeVisible();
      await expect(page.getByRole('button', { name: texts.nextDeparture })).toBeVisible();
      await expectNoAxeViolations(page);
      await capture(page, testInfo, 'fin-recorrido', lang);

      // End of the shift.
      await page.getByRole('button', { name: texts.end }).click();
      const dialog = page.getByRole('dialog', { name: texts.confirm });
      await expect(dialog).toBeVisible();
      await dialog.getByRole('button', { name: texts.yes, exact: true }).click();

      await expect(page).toHaveURL(/\/driver$/);
      await expect(page.getByRole('main').getByText(texts.ended)).toBeVisible();
      await expectNoAxeViolations(page);
      expect(backend.deletes).toBe(1);
      expect(
        await page.evaluate(() => sessionStorage.getItem('avisabus.driverSession')),
      ).toBeNull();
      expect(backend.unexpected).toEqual([]);
      expect(external).toEqual([]);
    });

    test(`[driver_ui.AC-11] rejects a wrong code and keeps the driver at /driver (${lang})`, async ({
      page,
    }) => {
      const backend = await mockDriver(page);
      await page.goto('/driver');

      await page.getByLabel(texts.code).fill('99998888');
      await page.getByRole('button', { name: texts.enter, exact: true }).click();

      await expect(page.getByText(texts.invalid)).toBeFocused();
      await expect(page).toHaveURL(/\/driver$/);
      expect(backend.unexpected).toEqual([]);
    });
  });
}
