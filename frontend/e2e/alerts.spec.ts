/// <reference lib="dom" />
/// <reference lib="dom.iterable" />
// Browser globals are only used inside page.evaluate() callbacks.
import AxeBuilder from '@axe-core/playwright';
import {
  expect,
  test,
  type Page,
  type Request,
  type TestInfo,
  type WebSocketRoute,
} from '@playwright/test';
import { fileURLToPath } from 'node:url';

import type { Alert } from '../src/shared/api/types';
import { ALERT_93, ARRIVALS_REALTIME, STOP_508 } from './fixtures';

const WCAG_21_AA = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];
const APP_ORIGIN = 'http://localhost:4173';
const TOKEN = 'AbCdEfGhIjKlMnOpQrStUv';
const STOP_URL = `/p/508?t=${TOKEN}`;
const DESTINATION = 'Passeig Marítim - Hospital Malva-rosa';

/**
 * Screenshots for the visual review of passenger_alert_ui.AC-13 (docs/design.md §5.3, §5.5,
 * §5.8, §7). Regenerated on every run (Playwright empties test-results/ first; not versioned):
 * frontend/test-results/passenger_alert_ui/<project>/<name>.png
 */
const CAPTURES_DIR = fileURLToPath(new URL('../test-results/passenger_alert_ui/', import.meta.url));

/** A request of line 93 whose bus is no longer among the arrivals (AC-08). */
const ORPHAN: Alert = {
  ...ALERT_93,
  alert_id: '9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d',
  trip_id: '12300',
  status: 'DELIVERED',
  needs: ['VISUAL'],
};

const TEXTS = {
  es: {
    arrivals: 'Próximas llegadas',
    request: 'Solicitar',
    requestLabel: `Solicitar parada a la línea 93 hacia ${DESTINATION}`,
    arrival: 'El autobús llega en 4 minutos.',
    ramp: 'Necesito la rampa',
    seat: 'Necesito un asiento',
    remember: 'Recordar mis necesidades en este dispositivo',
    confirm: 'Solicitar parada',
    back: 'Volver',
    requested: 'Parada solicitada para la línea 93',
    pending: 'Parada solicitada. Aún no hay conductor conectado en esta línea.',
    delivered: 'El conductor ha recibido tu solicitud.',
    indicated: 'Has indicado: rampa y asiento',
    cancel: 'Cancelar solicitud',
    cancelled: 'Solicitud cancelada',
    otherBus: 'Ya has solicitado otro autobús de esta línea',
    expired: 'Tu solicitud de la línea 93 ha terminado: el autobús ha pasado por la parada',
    rate: 'Has hecho demasiadas solicitudes. Inténtalo dentro de 2 minutos.',
    orphanTitle: `Línea 93 hacia ${DESTINATION}`,
    needsLink: 'Mis necesidades',
    needsTitle: 'Mis necesidades',
    save: 'Guardar',
    saved: 'Necesidades guardadas',
  },
  ca: {
    arrivals: 'Pròximes arribades',
    request: 'Sol·licita',
    requestLabel: `Sol·licita parada a la línia 93 cap a ${DESTINATION}`,
    arrival: "L'autobús arriba en 4 minuts.",
    ramp: 'Necessite la rampa',
    seat: 'Necessite un seient',
    remember: 'Recorda les meues necessitats en este dispositiu',
    confirm: 'Sol·licita la parada',
    back: 'Torna',
    requested: 'Parada sol·licitada per a la línia 93',
    pending: 'Parada sol·licitada. Encara no hi ha cap conductor connectat en esta línia.',
    delivered: 'El conductor ha rebut la teua sol·licitud.',
    indicated: 'Has indicat: rampa i seient',
    cancel: 'Cancel·la la sol·licitud',
    cancelled: 'Sol·licitud cancel·lada',
    otherBus: "Ja has sol·licitat un altre autobús d'esta línia",
    expired: "La teua sol·licitud de la línia 93 ha acabat: l'autobús ha passat per la parada",
    rate: "Has fet massa sol·licituds. Torna-ho a intentar d'ací a 2 minuts.",
    orphanTitle: `Línia 93 cap a ${DESTINATION}`,
    needsLink: 'Les meues necessitats',
    needsTitle: 'Les meues necessitats',
    save: 'Guarda',
    saved: 'Necessitats guardades',
  },
} as const;

type Lang = keyof typeof TEXTS;
type Reply = { status: number; body: unknown; headers?: Record<string, string> };

interface Backend {
  /** Device id received in the `hello` (null until then). */
  deviceId: string | null;
  socket: WebSocketRoute | null;
  posts: { body: unknown; deviceHeader: string | undefined }[];
  deletes: { path: string; deviceHeader: string | undefined }[];
  requests: Request[];
  unexpected: string[];
}

/**
 * Simulated API (`page.route`) and /ws/passenger (`page.routeWebSocket`): nothing leaves the
 * browser. The socket answers the `hello` with `snapshot`; the test sends events through
 * `backend.socket`.
 */
async function mockBackend(
  page: Page,
  { snapshot = [], post }: { snapshot?: Alert[]; post?: Reply } = {},
): Promise<Backend> {
  const backend: Backend = {
    deviceId: null,
    socket: null,
    posts: [],
    deletes: [],
    requests: [],
    unexpected: [],
  };
  page.on('request', (request) => backend.requests.push(request));
  await page.routeWebSocket('**/ws/passenger', (ws) => {
    backend.socket = ws;
    ws.onMessage((frame) => {
      const message = JSON.parse(String(frame)) as { type: string; device_id?: string };
      if (message.type !== 'hello') return;
      backend.deviceId = message.device_id ?? null;
      ws.send(JSON.stringify({ type: 'alerts.snapshot', alerts: snapshot }));
    });
  });
  await page.route('**/api/v1/**', async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const deviceHeader = request.headers()['x-device-id'];
    let reply: Reply;
    if (url.pathname === '/api/v1/stops/508') reply = { status: 200, body: STOP_508 };
    else if (url.pathname === '/api/v1/stops/508/arrivals')
      reply = { status: 200, body: ARRIVALS_REALTIME };
    else if (url.pathname === '/api/v1/alerts' && request.method() === 'POST') {
      const body = request.postDataJSON() as { needs: Alert['needs'] };
      backend.posts.push({ body, deviceHeader });
      reply = post ?? { status: 201, body: { ...ALERT_93, needs: body.needs } };
    } else if (url.pathname.startsWith('/api/v1/alerts/') && request.method() === 'DELETE') {
      backend.deletes.push({ path: url.pathname, deviceHeader });
      reply = { status: 204, body: null };
    } else {
      backend.unexpected.push(`${request.method()} ${url.pathname}`);
      reply = { status: 500, body: {} };
    }
    await route.fulfill({
      status: reply.status,
      headers: reply.headers,
      contentType: reply.status < 400 ? 'application/json' : 'application/problem+json',
      body: reply.body === null ? '' : JSON.stringify(reply.body),
    });
  });
  return backend;
}

/** No other origin, no unexpected API call and the device id never in a URL (AC-01). */
function expectPrivateAndLocal(backend: Backend) {
  expect(backend.unexpected).toEqual([]);
  for (const request of backend.requests) {
    expect(new URL(request.url()).origin).toBe(APP_ORIGIN);
    if (backend.deviceId !== null) expect(request.url()).not.toContain(backend.deviceId);
  }
}

/**
 * Full page, except with the dialog open: it is fixed to the viewport (bottom sheet on phones),
 * so a full-page capture would draw it in the middle of the page.
 */
async function capture(page: Page, testInfo: TestInfo, name: string, fullPage = true) {
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({
    path: `${CAPTURES_DIR}${testInfo.project.name}/${name}.png`,
    fullPage,
    animations: 'disabled',
    caret: 'hide',
  });
}

async function expectNoAxeViolations(page: Page) {
  const results = await new AxeBuilder({ page }).withTags(WCAG_21_AA).analyze();
  expect(results.violations).toEqual([]);
}

function cards(page: Page, lang: Lang) {
  return page.getByRole('region', { name: TEXTS[lang].arrivals }).getByRole('listitem');
}

function politeRegion(page: Page) {
  return page.locator('[aria-live="polite"]');
}

/** Opens the stop and waits for the arrivals and for the snapshot of the WebSocket. */
async function openStop(page: Page, lang: Lang, backend: Backend) {
  await page.goto(STOP_URL);
  await expect(cards(page, lang)).toHaveCount(5);
  await expect.poll(() => backend.deviceId).not.toBeNull();
}

test.use({ serviceWorkers: 'block' });

for (const [lang, locale] of [
  ['es', 'es-ES'],
  ['ca', 'ca-ES'],
] as const) {
  test.describe(`stop requests in ${lang}`, () => {
    test.use({ locale });
    const texts = TEXTS[lang];

    test(`[passenger_alert_ui.AC-03] [passenger_alert_ui.AC-04] [passenger_alert_ui.AC-05] [passenger_alert_ui.AC-12] [passenger_alert_ui.AC-13] requests a stop with needs after confirming (${lang})`, async ({
      page,
    }, testInfo) => {
      const backend = await mockBackend(page);
      await openStop(page, lang, backend);

      const request = cards(page, lang).nth(1).getByRole('button', { name: texts.requestLabel });
      await expect(request).toHaveText(texts.request);
      const box = await request.boundingBox();
      expect(box?.height).toBeGreaterThanOrEqual(48);
      await expectNoAxeViolations(page);
      await capture(page, testInfo, `stop-request-buttons-${lang}`);

      await request.click();
      const dialog = page.getByRole('dialog', { name: texts.requestLabel });
      await expect(dialog).toBeVisible();
      await expect(dialog.getByRole('heading', { level: 2 })).toBeFocused();
      await expect(dialog).toContainText(texts.arrival);
      await expectNoAxeViolations(page);
      await capture(page, testInfo, `dialog-open-${lang}`, false);

      await dialog.getByRole('checkbox', { name: texts.ramp }).check();
      await dialog.getByRole('checkbox', { name: texts.seat }).check();
      await dialog.getByRole('button', { name: texts.confirm }).click();

      await expect(dialog).toBeHidden();
      const card = cards(page, lang).nth(1);
      await expect(card).toContainText(texts.pending);
      await expect(card.getByText(texts.indicated)).toBeVisible();
      await expect(card.getByRole('button', { name: texts.cancel })).toBeFocused();
      await expect(politeRegion(page)).toHaveText(texts.requested);
      await expect(cards(page, lang).nth(3)).toContainText(texts.otherBus);
      expect(backend.posts).toHaveLength(1);
      expect(backend.posts[0]?.body).toEqual({
        stop_id: '508',
        token: TOKEN,
        line: '93',
        direction_id: 0,
        trip_id: '12345',
        service_date: '2026-11-04',
        needs: ['RAMP', 'SEAT'],
      });
      expect(backend.posts[0]?.deviceHeader).toBe(backend.deviceId);
      const cancelBox = await card.getByRole('button', { name: texts.cancel }).boundingBox();
      expect(cancelBox?.height).toBeGreaterThanOrEqual(48);

      await expectNoAxeViolations(page);
      await capture(page, testInfo, `card-requested-${lang}`);
      expectPrivateAndLocal(backend);
    });

    test(`[passenger_alert_ui.AC-11] [passenger_alert_ui.AC-12] [passenger_alert_ui.AC-13] an expiry event ends the request and gives the focus back to "Solicitar" (${lang})`, async ({
      page,
    }, testInfo) => {
      const backend = await mockBackend(page, { snapshot: [ALERT_93] });
      await openStop(page, lang, backend);
      const card = cards(page, lang).nth(1);
      const cancel = card.getByRole('button', { name: texts.cancel });
      await expect(card).toContainText(texts.pending);
      await cancel.focus();

      backend.socket?.send(
        JSON.stringify({ type: 'alert.expired', alert_id: ALERT_93.alert_id, reason: 'PASSED' }),
      );

      await expect(cancel).toHaveCount(0);
      await expect(politeRegion(page)).toHaveText(texts.expired);
      await expect(card.getByRole('button', { name: texts.requestLabel })).toBeFocused();
      await expectNoAxeViolations(page);
      await capture(page, testInfo, `card-expired-${lang}`);
      expectPrivateAndLocal(backend);
    });

    test(`[passenger_alert_ui.AC-09] [passenger_alert_ui.AC-12] cancels the request without confirmation (${lang})`, async ({
      page,
    }) => {
      const backend = await mockBackend(page, { snapshot: [ALERT_93] });
      await openStop(page, lang, backend);
      const card = cards(page, lang).nth(1);

      await card.getByRole('button', { name: texts.cancel }).click();

      await expect(card.getByRole('button', { name: texts.requestLabel })).toBeFocused();
      await expect(page.getByRole('dialog')).toHaveCount(0);
      await expect(politeRegion(page)).toHaveText(texts.cancelled);
      expect(backend.deletes).toEqual([
        { path: `/api/v1/alerts/${ALERT_93.alert_id}`, deviceHeader: backend.deviceId },
      ]);
      expectPrivateAndLocal(backend);
    });

    test(`[passenger_alert_ui.AC-06] [passenger_alert_ui.AC-12] [passenger_alert_ui.AC-13] a 429 keeps the dialog open with the waiting time (${lang})`, async ({
      page,
    }, testInfo) => {
      const backend = await mockBackend(page, {
        post: {
          status: 429,
          body: { type: 'https://avisabus/problems/rate-limited', title: 'x', status: 429 },
          headers: { 'Retry-After': '120' },
        },
      });
      await openStop(page, lang, backend);

      await cards(page, lang).nth(1).getByRole('button', { name: texts.requestLabel }).click();
      const dialog = page.getByRole('dialog', { name: texts.requestLabel });
      await dialog.getByRole('button', { name: texts.confirm }).click();

      const alert = dialog.getByRole('alert');
      await expect(alert).toHaveText(texts.rate);
      await expect(alert).toBeFocused();
      await expect(dialog).toBeVisible();
      await expect(dialog.getByRole('button', { name: texts.confirm })).toBeEnabled();
      await expectNoAxeViolations(page);
      await capture(page, testInfo, `dialog-error-429-${lang}`, false);
      expectPrivateAndLocal(backend);
    });

    test(`[passenger_alert_ui.AC-08] [passenger_alert_ui.AC-12] [passenger_alert_ui.AC-13] shows a request whose bus is no longer in the list (${lang})`, async ({
      page,
    }, testInfo) => {
      const backend = await mockBackend(page, { snapshot: [ORPHAN] });
      await openStop(page, lang, backend);

      const section = page.getByRole('region', { name: texts.arrivals });
      await expect(section.getByText(texts.orphanTitle)).toBeVisible();
      await expect(section).toContainText(texts.delivered);
      await expect(section.getByRole('button', { name: texts.cancel })).toHaveCount(1);
      await expect(cards(page, lang).nth(1)).toContainText(texts.otherBus);
      await expectNoAxeViolations(page);
      await capture(page, testInfo, `orphan-request-${lang}`);
      expectPrivateAndLocal(backend);
    });

    test(`[passenger_alert_ui.AC-02] [passenger_alert_ui.AC-12] [passenger_alert_ui.AC-13] "Mis necesidades" keeps the profile on the device (${lang})`, async ({
      page,
    }, testInfo) => {
      const backend = await mockBackend(page);
      await page.goto('/');

      await page.getByRole('link', { name: texts.needsLink }).click();
      await expect(page.getByRole('heading', { level: 1 })).toHaveText(texts.needsTitle);
      await expect(page.getByRole('heading', { level: 1 })).toBeFocused();
      await page.getByRole('checkbox', { name: texts.ramp }).check();
      await page.getByRole('button', { name: texts.save }).click();
      await expect(politeRegion(page)).toHaveText(texts.saved);
      await expectNoAxeViolations(page);
      await capture(page, testInfo, `needs-page-${lang}`);

      await page.reload();
      await expect(page.getByRole('checkbox', { name: texts.ramp })).toBeChecked();
      await expect(page.getByRole('checkbox', { name: texts.seat })).not.toBeChecked();
      // Only on the device: the page never calls the API.
      expect(backend.requests.filter((r) => r.url().includes('/api/'))).toEqual([]);

      // The profile is preloaded in the request dialog.
      await openStop(page, lang, backend);
      await cards(page, lang).nth(1).getByRole('button', { name: texts.requestLabel }).click();
      const dialog = page.getByRole('dialog', { name: texts.requestLabel });
      await expect(dialog.getByRole('checkbox', { name: texts.ramp })).toBeChecked();
      await expect(dialog.getByRole('checkbox', { name: texts.remember })).not.toBeChecked();
      expectPrivateAndLocal(backend);
    });
  });
}

test.describe('request dialog with the keyboard', () => {
  test.use({ locale: 'es-ES' });
  const texts = TEXTS.es;

  test('[passenger_alert_ui.AC-04] [passenger_alert_ui.AC-12] opens on the title, keeps the focus inside and gives it back on Escape and "Volver"', async ({
    page,
    browserName,
  }) => {
    // WebKit (Safari, iPhone, iPad) only tabs to buttons and checkboxes with Option+Tab, as
    // with "Full Keyboard Access" off; Chromium tabs to every control.
    const tab = browserName === 'webkit' ? 'Alt+Tab' : 'Tab';
    const backend = await mockBackend(page);
    await openStop(page, 'es', backend);
    const request = cards(page, 'es').nth(1).getByRole('button', { name: texts.requestLabel });
    const dialog = page.getByRole('dialog', { name: texts.requestLabel });
    const focusInDialog = () =>
      page.evaluate(() => document.querySelector('dialog')?.contains(document.activeElement));

    await request.focus();
    await page.keyboard.press('Enter');
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole('heading', { level: 2 })).toBeFocused();

    // Four needs, "Recordar…", "Solicitar parada" and "Volver": the focus never leaves.
    for (let i = 0; i < 7; i += 1) {
      await page.keyboard.press(tab);
      expect(await focusInDialog()).toBe(true);
    }
    await expect(dialog.getByRole('button', { name: texts.back })).toBeFocused();
    for (let i = 0; i < 6; i += 1) {
      await page.keyboard.press(`Shift+${tab}`);
      expect(await focusInDialog()).toBe(true);
    }
    await expect(dialog.getByRole('checkbox', { name: texts.ramp })).toBeFocused();

    await page.keyboard.press('Escape');
    await expect(dialog).toBeHidden();
    await expect(request).toBeFocused();

    await page.keyboard.press('Enter');
    await expect(dialog.getByRole('heading', { level: 2 })).toBeFocused();
    await dialog.getByRole('button', { name: texts.back }).focus();
    await page.keyboard.press('Enter');
    await expect(dialog).toBeHidden();
    await expect(request).toBeFocused();
    expect(backend.posts).toEqual([]);
    expectPrivateAndLocal(backend);
  });
});
