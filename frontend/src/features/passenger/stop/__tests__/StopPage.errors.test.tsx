import { act, fireEvent, screen, within } from '@testing-library/react';
import { RouterProvider, createMemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { routes } from '../../../../app/routes';
import type { Language } from '../../../../shared/i18n/languages';
import { ARRIVALS_REALTIME, STOP_508 } from '../../../../test/fixtures/api';
import {
  NETWORK_UNAVAILABLE,
  NetworkFailure,
  STOP_NOT_FOUND,
  deferred,
  mockApi,
  ok,
  problem,
  type FakeReply,
} from '../../../../test/mockApi';
import { renderWithProviders } from '../../../../test/render';

const TOKEN = 'AbCdEfGhIjKlMnOpQrStUv';
const GENERATED_AT = Date.parse('2026-11-04T07:40:00Z');
/** Retries of a failed request (1 s and 2 s apart) before the error is shown. */
const RETRIES_MS = 3_100;

type Reply = () => FakeReply | Promise<FakeReply>;

function renderAt(path: string, language: Language = 'es') {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  return renderWithProviders(<RouterProvider router={router} />, { language });
}

async function flush(ms = 0) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

function setOnline(online: boolean) {
  vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(online);
  window.dispatchEvent(new Event(online ? 'online' : 'offline'));
}

function arrivalsList(): HTMLElement | null {
  const section = screen
    .getByRole('heading', { level: 2, name: 'Próximas llegadas' })
    .closest('section')!;
  return within(section).queryByRole('list');
}

function politeRegion(): HTMLElement {
  const region = document.querySelector<HTMLElement>('[aria-live="polite"]');
  if (region === null) throw new Error('no polite region');
  return region;
}

/** Puts the keyboard focus on a button and activates it, as a keyboard or screen reader user. */
function press(name: string): HTMLElement {
  const button = screen.getByRole('button', { name });
  button.focus();
  fireEvent.click(button);
  return button;
}

function offlineNotice(): HTMLElement | null {
  const text = screen.queryByText('Sin conexión.');
  return text?.closest<HTMLElement>('[role="status"]') ?? null;
}

describe('StopPage errors and connectivity', () => {
  let stopReply: Reply;
  let arrivalsReply: Reply;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(GENERATED_AT);
    stopReply = () => ok(STOP_508());
    arrivalsReply = () => ok(ARRIVALS_REALTIME());
  });

  afterEach(() => {
    act(() => setOnline(true));
    vi.restoreAllMocks();
    vi.useRealTimers();
    vi.unstubAllGlobals();
    document.title = '';
  });

  function api() {
    return mockApi((url) => {
      if (url.pathname === '/api/v1/stops/508') return stopReply();
      if (url.pathname === '/api/v1/stops/508/arrivals') return arrivalsReply();
      throw new Error(`unexpected request ${url.pathname}`);
    });
  }

  it.each([
    ['stop', 'es', 'Parada no encontrada', 'Vuelve a escanear el código QR de la parada'],
    ['arrivals', 'es', 'Parada no encontrada', 'Vuelve a escanear el código QR de la parada'],
    ['stop', 'ca', 'Parada no trobada', 'Torna a escanejar el codi QR de la parada'],
  ] as const)(
    '[passenger_stop_view.AC-16] a 404 of the %s request shows "Parada no encontrada" without the stop id or token (%s)',
    async (failing, language, title, body) => {
      if (failing === 'stop') stopReply = () => problem(404, STOP_NOT_FOUND);
      else arrivalsReply = () => problem(404, STOP_NOT_FOUND);
      api();
      renderAt(`/p/508?t=${TOKEN}`, language);
      await flush();

      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(title);
      expect(screen.getByText(new RegExp(body))).toBeInTheDocument();
      expect(document.title).toBe(`${title} · AvisaBus`);
      const main = screen.getByRole('main');
      expect(main).not.toHaveTextContent('508');
      expect(main).not.toHaveTextContent(TOKEN);
      expect(screen.queryByRole('list')).toBeNull();
    },
  );

  it('[passenger_stop_view.AC-16] a 404 is neither retried nor refreshed', async () => {
    stopReply = () => problem(404, STOP_NOT_FOUND);
    arrivalsReply = () => problem(404, STOP_NOT_FOUND);
    const { fetchMock } = api();
    renderAt(`/p/508?t=${TOKEN}`);

    await flush(120_000);

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Parada no encontrada');
  });

  it('[passenger_stop_view.AC-16] without a token shows "Parada no encontrada" and does not call the API', async () => {
    const { fetchMock } = api();
    renderAt('/p/508');
    await flush();

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Parada no encontrada');
    expect(screen.getByRole('main')).not.toHaveTextContent('508');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([
    ['503', () => problem(503, NETWORK_UNAVAILABLE)],
    ['network error', () => Promise.reject(new NetworkFailure())],
  ] as const)(
    '[passenger_stop_view.AC-17] a %s while loading the arrivals shows a message with "Reintentar"',
    async (_name, failure) => {
      arrivalsReply = failure;
      const { arrivalCalls } = api();
      renderAt(`/p/508?t=${TOKEN}`);
      await flush(RETRIES_MS);

      expect(arrivalCalls()).toBe(3);
      expect(screen.getByText('No se han podido cargar los datos.')).toBeInTheDocument();
      expect(arrivalsList()).toBeNull();

      arrivalsReply = () => ok(ARRIVALS_REALTIME());
      fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
      await flush();

      expect(arrivalsList()).not.toBeNull();
      expect(screen.queryByText('No se han podido cargar los datos.')).toBeNull();
      expect(screen.queryByRole('button', { name: 'Reintentar' })).toBeNull();
    },
  );

  it('[passenger_stop_view.AC-17] a 503 while loading the stop shows the message and retries both requests', async () => {
    stopReply = () => problem(503, NETWORK_UNAVAILABLE);
    arrivalsReply = () => problem(503, NETWORK_UNAVAILABLE);
    const { calls } = api();
    renderAt(`/p/508?t=${TOKEN}`);
    await flush(RETRIES_MS);

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Parada');
    expect(screen.getByText('No se han podido cargar los datos.')).toBeInTheDocument();

    stopReply = () => ok(STOP_508());
    arrivalsReply = () => ok(ARRIVALS_REALTIME());
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
    await flush();

    expect(calls('/stops/508?')).toBe(4);
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent("Parc de l'Oest - Enguera");
    expect(arrivalsList()).not.toBeNull();
  });

  it.each([
    ['es', 'Datos de las 08:40, pueden no estar actualizados', 'Reintentar'],
    ['ca', 'Dades de les 08:40, poden no estar actualitzades', 'Reintenta'],
  ] as const)(
    '[passenger_stop_view.AC-17] keeps the previous data marked as possibly outdated when a refresh fails (%s)',
    async (language, stale, retry) => {
      api();
      renderAt(`/p/508?t=${TOKEN}`, language);
      await flush();

      arrivalsReply = () => Promise.reject(new NetworkFailure());
      await flush(20_000 + RETRIES_MS);

      expect(screen.getByText(stale)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: retry })).toBeInTheDocument();
      expect(screen.getAllByRole('listitem').length).toBeGreaterThanOrEqual(5);

      arrivalsReply = () => ok(ARRIVALS_REALTIME());
      fireEvent.click(screen.getByRole('button', { name: retry }));
      await flush();
      expect(screen.queryByText(stale)).toBeNull();
    },
  );

  it('[passenger_stop_view.AC-17] when only the stop request fails, the message speaks of the data and "Reintentar" asks for the stop again', async () => {
    stopReply = () => problem(503, NETWORK_UNAVAILABLE);
    const { calls } = api();
    renderAt(`/p/508?t=${TOKEN}`);
    await flush(RETRIES_MS);

    expect(calls('/stops/508?')).toBe(3);
    expect(screen.getByText('No se han podido cargar los datos.')).toBeInTheDocument();
    expect(screen.queryByText(/las llegadas/)).toBeNull();
    expect(arrivalsList()).not.toBeNull();

    stopReply = () => ok(STOP_508());
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
    await flush();

    expect(calls('/stops/508?')).toBe(4);
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent("Parc de l'Oest - Enguera");
    expect(screen.queryByText('No se han podido cargar los datos.')).toBeNull();
    expect(screen.queryByRole('button', { name: 'Reintentar' })).toBeNull();
  });

  it('[passenger_stop_view.AC-17] the error message speaks of the data in Valencian too', async () => {
    arrivalsReply = () => problem(503, NETWORK_UNAVAILABLE);
    api();
    renderAt(`/p/508?t=${TOKEN}`, 'ca');
    await flush(RETRIES_MS);

    expect(screen.getByText("No s'han pogut carregar les dades.")).toBeInTheDocument();
  });

  it.each([
    ['es', 'Actualizar', 'Reintentar', 'No se han podido actualizar los datos'],
    ['ca', 'Actualitza', 'Reintenta', "No s'han pogut actualitzar les dades"],
  ] as const)(
    '[passenger_stop_view.AC-24] a failed "Actualizar" is announced and moves the focus to "Reintentar" (%s)',
    async (language, refresh, retry, failed) => {
      api();
      renderAt(`/p/508?t=${TOKEN}`, language);
      await flush();

      arrivalsReply = () => problem(503, NETWORK_UNAVAILABLE);
      press(refresh);
      await flush(RETRIES_MS);
      await flush(100);

      expect(politeRegion()).toHaveTextContent(failed);
      expect(document.activeElement).toBe(screen.getByRole('button', { name: retry }));
      expect(screen.queryByRole('button', { name: refresh })).toBeNull();
    },
  );

  it.each([
    ['the arrivals', 'arrivals'],
    ['the stop', 'stop'],
    ['the refresh of the arrivals', 'refresh'],
  ] as const)(
    '[passenger_stop_view.AC-24] a successful "Reintentar" after a failure of %s announces "Datos actualizados" and moves the focus to "Actualizar"',
    async (_name, failing) => {
      if (failing === 'stop') stopReply = () => problem(503, NETWORK_UNAVAILABLE);
      if (failing === 'arrivals') arrivalsReply = () => problem(503, NETWORK_UNAVAILABLE);
      api();
      renderAt(`/p/508?t=${TOKEN}`);
      await flush(RETRIES_MS);
      if (failing === 'refresh') {
        arrivalsReply = () => Promise.reject(new NetworkFailure());
        await flush(20_000 + RETRIES_MS);
      }
      await flush(100);
      expect(politeRegion()).toHaveTextContent('');

      stopReply = () => ok(STOP_508());
      arrivalsReply = () => ok(ARRIVALS_REALTIME());
      press('Reintentar');
      await flush();
      await flush(100);

      expect(politeRegion()).toHaveTextContent('Datos actualizados');
      expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Actualizar' }));
    },
  );

  it.each([
    ['the arrivals', 'arrivals'],
    ['the stop', 'stop'],
  ] as const)(
    '[passenger_stop_view.AC-24] a failed "Reintentar" after a failure of %s is announced and keeps the focus on "Reintentar"',
    async (_name, failing) => {
      if (failing === 'stop') stopReply = () => problem(503, NETWORK_UNAVAILABLE);
      else arrivalsReply = () => problem(503, NETWORK_UNAVAILABLE);
      api();
      renderAt(`/p/508?t=${TOKEN}`);
      await flush(RETRIES_MS);

      const pending = deferred<FakeReply>();
      if (failing === 'stop') stopReply = () => pending.promise;
      else arrivalsReply = () => pending.promise;
      const button = press('Reintentar');
      await flush(100);
      // While the request is in flight the button stays where the focus is.
      expect(document.activeElement).toBe(button);
      expect(politeRegion()).toHaveTextContent('');

      if (failing === 'stop') stopReply = () => problem(503, NETWORK_UNAVAILABLE);
      else arrivalsReply = () => problem(503, NETWORK_UNAVAILABLE);
      pending.resolve(problem(503, NETWORK_UNAVAILABLE));
      await flush(RETRIES_MS);
      await flush(100);

      expect(politeRegion()).toHaveTextContent('No se han podido actualizar los datos');
      expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Reintentar' }));
    },
  );

  it('[passenger_stop_view.AC-17] [passenger_stop_view.AC-15] [passenger_stop_view.AC-24] a failed automatic refresh is not announced', async () => {
    api();
    renderAt(`/p/508?t=${TOKEN}`);
    await flush();

    arrivalsReply = () => problem(503, NETWORK_UNAVAILABLE);
    await flush(20_000 + RETRIES_MS);
    await flush(100);

    expect(screen.getByText('No se han podido cargar los datos.')).toBeInTheDocument();
    const live = document.querySelectorAll('[aria-live]');
    live.forEach((region) => expect(region).toHaveTextContent(''));
  });

  function liveRegions(): HTMLElement[] {
    return [...document.querySelectorAll<HTMLElement>('[aria-live]')];
  }

  it.each([
    ['"Actualizar"', 'es', 'refresh', 'Actualizar', 'Parada no encontrada'],
    ['"Actualitza"', 'ca', 'refresh', 'Actualitza', 'Parada no trobada'],
    [
      '"Reintentar" after a failure of the arrivals',
      'es',
      'arrivals',
      'Reintentar',
      'Parada no encontrada',
    ],
    [
      '"Reintentar" after a failure of the stop',
      'es',
      'stop',
      'Reintentar',
      'Parada no encontrada',
    ],
    [
      '"Reintenta" after a failure of the arrivals',
      'ca',
      'arrivals',
      'Reintenta',
      'Parada no trobada',
    ],
  ] as const)(
    '[passenger_stop_view.AC-24] [passenger_stop_view.AC-16] %s answered with a 404 moves the focus to the "Parada no encontrada" h1 without announcement (%s)',
    async (_name, language, failing, button, title) => {
      if (failing === 'stop') stopReply = () => problem(503, NETWORK_UNAVAILABLE);
      if (failing === 'arrivals') arrivalsReply = () => problem(503, NETWORK_UNAVAILABLE);
      api();
      renderAt(`/p/508?t=${TOKEN}`, language);
      await flush(RETRIES_MS);
      await flush(100);

      if (failing === 'stop') stopReply = () => problem(404, STOP_NOT_FOUND);
      else arrivalsReply = () => problem(404, STOP_NOT_FOUND);
      press(button);
      await flush();
      await flush(100);

      const heading = screen.getByRole('heading', { level: 1 });
      expect(heading).toHaveTextContent(title);
      expect(document.activeElement).toBe(heading);
      liveRegions().forEach((region) => expect(region).toHaveTextContent(''));
    },
  );

  it('[passenger_stop_view.AC-16] [passenger_stop_view.AC-24] a 404 on load does not take the focus', async () => {
    arrivalsReply = () => problem(404, STOP_NOT_FOUND);
    api();
    renderAt(`/p/508?t=${TOKEN}`);
    await flush();
    await flush(100);

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Parada no encontrada');
    expect(document.activeElement).toBe(document.body);
  });

  it.each([
    ['es', 'Actualizar', 'Reintentar'],
    ['ca', 'Actualitza', 'Reintenta'],
  ] as const)(
    '[passenger_stop_view.AC-24] with the focus on "Reintentar", an automatic refresh that succeeds moves it to "Actualizar" without announcement (%s)',
    async (language, refresh, retry) => {
      api();
      renderAt(`/p/508?t=${TOKEN}`, language);
      await flush();
      arrivalsReply = () => problem(503, NETWORK_UNAVAILABLE);
      await flush(20_000 + RETRIES_MS);
      await flush(100);
      screen.getByRole('button', { name: retry }).focus();

      arrivalsReply = () => ok(ARRIVALS_REALTIME());
      await flush(20_000);
      await flush(100);

      expect(screen.queryByRole('button', { name: retry })).toBeNull();
      expect(document.activeElement).toBe(screen.getByRole('button', { name: refresh }));
      liveRegions().forEach((region) => expect(region).toHaveTextContent(''));
    },
  );

  it('[passenger_stop_view.AC-24] after a failed "Actualizar", an automatic refresh that succeeds moves the focus back to "Actualizar" without announcing it', async () => {
    api();
    renderAt(`/p/508?t=${TOKEN}`);
    await flush();
    arrivalsReply = () => problem(503, NETWORK_UNAVAILABLE);
    press('Actualizar');
    await flush(RETRIES_MS);
    await flush(100);
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Reintentar' }));
    expect(politeRegion()).toHaveTextContent('No se han podido actualizar los datos');

    arrivalsReply = () => ok(ARRIVALS_REALTIME());
    await flush(20_000);
    await flush(100);

    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Actualizar' }));
    expect(politeRegion()).not.toHaveTextContent('Datos actualizados');
  });

  it('[passenger_stop_view.AC-24] without data yet, "Reintentar" keeps the focus while an automatic refresh is in flight and hands it to "Actualizar" when it succeeds', async () => {
    arrivalsReply = () => problem(503, NETWORK_UNAVAILABLE);
    const { arrivalCalls } = api();
    renderAt(`/p/508?t=${TOKEN}`);
    await flush(RETRIES_MS);
    await flush(100);
    const button = screen.getByRole('button', { name: 'Reintentar' });
    button.focus();

    const pending = deferred<FakeReply>();
    arrivalsReply = () => pending.promise;
    await flush(20_000);
    expect(arrivalCalls()).toBe(4);
    // The automatic request is in flight: the error notice and its button stay.
    expect(screen.getByText('No se han podido cargar los datos.')).toBeInTheDocument();
    expect(document.activeElement).toBe(button);

    pending.resolve(ok(ARRIVALS_REALTIME()));
    await flush();
    await flush(100);

    expect(arrivalsList()).not.toBeNull();
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Actualizar' }));
    liveRegions().forEach((region) => expect(region).toHaveTextContent(''));
  });

  it('[passenger_stop_view.AC-24] [passenger_stop_view.AC-18] without data yet and without connection, "Reintentar" keeps the focus and hands it to "Actualizar" when the data arrive', async () => {
    arrivalsReply = () => problem(503, NETWORK_UNAVAILABLE);
    api();
    renderAt(`/p/508?t=${TOKEN}`);
    await flush(RETRIES_MS);
    await flush(100);
    const button = screen.getByRole('button', { name: 'Reintentar' });
    button.focus();

    act(() => setOnline(false));
    await flush(60_000);
    expect(offlineNotice()).not.toBeNull();
    expect(screen.getByText('No se han podido cargar los datos.')).toBeInTheDocument();
    expect(document.activeElement).toBe(button);

    arrivalsReply = () => ok(ARRIVALS_REALTIME());
    act(() => setOnline(true));
    await flush();
    await flush(100);

    expect(arrivalsList()).not.toBeNull();
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Actualizar' }));
    liveRegions().forEach((region) => expect(region).toHaveTextContent(''));
  });

  it.each([
    ['stays on body', false],
    ['was moved by the person', true],
  ] as const)(
    '[passenger_stop_view.AC-24] when "Reintentar" disappears before "Actualizar" exists, the focus goes to "Actualizar" only if it %s',
    async (_name, personMovesFocus) => {
      // Only the stop fails while the first arrivals are still on their way.
      stopReply = () => problem(503, NETWORK_UNAVAILABLE);
      const firstArrivals = deferred<FakeReply>();
      arrivalsReply = () => firstArrivals.promise;
      api();
      renderAt(`/p/508?t=${TOKEN}`);
      await flush(RETRIES_MS);
      await flush(100);
      screen.getByRole('button', { name: 'Reintentar' }).focus();

      // Reconnecting asks again for the stop automatically; it succeeds.
      stopReply = () => ok(STOP_508());
      act(() => setOnline(false));
      act(() => setOnline(true));
      await flush();
      await flush(100);
      expect(screen.queryByRole('button', { name: 'Reintentar' })).toBeNull();
      const skipLink = screen.getByRole('link', { name: 'Saltar al contenido' });
      if (personMovesFocus) skipLink.focus();

      firstArrivals.resolve(ok(ARRIVALS_REALTIME()));
      await flush();
      await flush(100);

      const refresh = screen.getByRole('button', { name: 'Actualizar' });
      expect(document.activeElement).toBe(personMovesFocus ? skipLink : refresh);
    },
  );

  it('[passenger_stop_view.AC-24] an automatic refresh that succeeds does not take the focus when it was not on "Reintentar"', async () => {
    api();
    renderAt(`/p/508?t=${TOKEN}`);
    await flush();
    arrivalsReply = () => problem(503, NETWORK_UNAVAILABLE);
    await flush(20_000 + RETRIES_MS);
    await flush(100);
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeInTheDocument();
    expect(document.activeElement).toBe(document.body);

    arrivalsReply = () => ok(ARRIVALS_REALTIME());
    await flush(20_000);
    await flush(100);

    expect(screen.getByRole('button', { name: 'Actualizar' })).toBeInTheDocument();
    expect(document.activeElement).toBe(document.body);
  });

  it('[passenger_stop_view.AC-18] shows "Sin conexión" as a status and does not retry until the connection is back', async () => {
    const { arrivalCalls } = api();
    renderAt(`/p/508?t=${TOKEN}`);
    await flush();
    expect(offlineNotice()).toBeNull();
    expect(arrivalCalls()).toBe(1);

    act(() => setOnline(false));
    await flush();
    expect(offlineNotice()).toHaveTextContent('Sin conexión.');
    await flush(120_000);
    expect(arrivalCalls()).toBe(1);
    // The data already shown stay.
    expect(arrivalsList()).not.toBeNull();

    act(() => setOnline(true));
    await flush();
    expect(offlineNotice()).toBeNull();
    expect(arrivalCalls()).toBe(2);
  });

  it('[passenger_stop_view.AC-18] opened without connection, it waits for it before calling the API', async () => {
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    const { fetchMock } = api();
    renderAt(`/p/508?t=${TOKEN}`, 'ca');
    await flush(60_000);

    expect(screen.getByText('Sense connexió.').closest('[role="status"]')).not.toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();

    act(() => setOnline(true));
    await flush();
    expect(fetchMock).toHaveBeenCalled();
    expect(screen.queryByText('Sense connexió.')).toBeNull();
  });
});
