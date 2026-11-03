import { act, fireEvent, screen, within } from '@testing-library/react';
import { RouterProvider, createMemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { routes } from '../../../../app/routes';
import type { Language } from '../../../../shared/i18n/languages';
import { ARRIVALS_REALTIME, STOP_508 } from '../../../../test/fixtures/api';
import {
  STOP_NOT_FOUND,
  deferred,
  mockApi,
  ok,
  problem,
  setVisibility,
  type FakeReply,
} from '../../../../test/mockApi';
import { renderWithProviders } from '../../../../test/render';
import { getLastStop } from '../lastStop';
import { spokenText } from './helpers';

const TOKEN = 'AbCdEfGhIjKlMnOpQrStUv';
const GENERATED_AT = Date.parse('2026-11-04T07:40:00Z');

function renderStop(language: Language = 'es', path = `/p/508?t=${TOKEN}`) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  return renderWithProviders(<RouterProvider router={router} />, { language });
}

/** Lets pending promises and due timers run (fake timers). */
async function flush(ms = 0) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

function politeRegion(): HTMLElement {
  const region = document.querySelector<HTMLElement>('[aria-live="polite"]');
  if (region === null) throw new Error('no polite region');
  return region;
}

function arrivalItems(): HTMLElement[] {
  const heading = screen.getByRole('heading', { level: 2, name: 'Próximas llegadas' });
  const section = heading.closest('section');
  if (section === null) throw new Error('no arrivals section');
  return within(section).getAllByRole('listitem');
}

describe('StopPage', () => {
  let stopReply: () => FakeReply;
  let arrivalsReply: () => FakeReply | Promise<FakeReply>;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(GENERATED_AT);
    stopReply = () => ok(STOP_508());
    arrivalsReply = () => ok(ARRIVALS_REALTIME());
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    setVisibility('visible');
    localStorage.clear();
    document.title = '';
  });

  function api() {
    return mockApi((url) => {
      if (url.pathname === '/api/v1/stops/508') return stopReply();
      if (url.pathname === '/api/v1/stops/508/arrivals') return arrivalsReply();
      throw new Error(`unexpected request ${url.pathname}`);
    });
  }

  it('[passenger_stop_view.AC-04] shows the stop name as h1, its code, its lines and the document title', async () => {
    const { fetchMock } = api();
    renderStop();
    await flush();

    const h1 = screen.getByRole('heading', { level: 1 });
    expect(h1).toHaveTextContent("Parc de l'Oest - Enguera");
    expect(within(h1).getByText("Parc de l'Oest - Enguera")).toHaveAttribute(
      'lang',
      'ca-ES-valencia',
    );
    expect(screen.getByText('Parada 508')).toBeInTheDocument();
    const lines = screen.getByRole('heading', { level: 2, name: 'Líneas' }).closest('section')!;
    expect(
      within(lines)
        .getAllByRole('listitem')
        .map((li) => li.textContent),
    ).toEqual(['Línea 7070', 'Línea 9393']);
    expect(document.title).toBe("Parc de l'Oest - Enguera · AvisaBus");
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe(`/api/v1/stops/508?t=${TOKEN}`);
  });

  it('[passenger_stop_view.AC-04] shows the arrivals of the stop in Valencian too', async () => {
    api();
    renderStop('ca');
    await flush();

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent("Parc de l'Oest - Enguera");
    expect(screen.getByRole('heading', { level: 2, name: 'Línies' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 2, name: 'Pròximes arribades' })).toBeVisible();
    expect(document.title).toBe("Parc de l'Oest - Enguera · AvisaBus");
  });

  it('[passenger_stop_view.AC-19] remembers the stop id, name and token once the stop has loaded', async () => {
    api();
    expect(getLastStop()).toBeNull();

    renderStop();
    await flush();

    expect(getLastStop()).toEqual({
      stopId: '508',
      name: "Parc de l'Oest - Enguera",
      token: TOKEN,
    });
  });

  it('[passenger_stop_view.AC-19] does not remember a stop that was not found', async () => {
    stopReply = () => problem(404, STOP_NOT_FOUND);
    arrivalsReply = () => problem(404, STOP_NOT_FOUND);
    api();

    renderStop();
    await flush();

    expect(getLastStop()).toBeNull();
  });

  it('[passenger_stop_view.AC-12] refreshes every refresh_after_s seconds without clearing the list', async () => {
    const { arrivalCalls } = api();
    renderStop();
    await flush();
    expect(arrivalCalls()).toBe(1);
    expect(arrivalItems()).toHaveLength(5);

    await flush(19_999);
    expect(arrivalCalls()).toBe(1);

    const pending = deferred<FakeReply>();
    arrivalsReply = () => pending.promise;
    await flush(1);
    expect(arrivalCalls()).toBe(2);
    // While the new data arrive, the previous list stays.
    expect(arrivalItems()).toHaveLength(5);

    const next = ARRIVALS_REALTIME();
    next.arrivals = next.arrivals.slice(0, 2);
    pending.resolve(ok(next));
    await flush();
    expect(arrivalItems()).toHaveLength(2);
  });

  it('[passenger_stop_view.AC-12] never waits more than 30 s between refreshes', async () => {
    arrivalsReply = () => ok({ ...ARRIVALS_REALTIME(), refresh_after_s: 45 });
    const { arrivalCalls } = api();
    renderStop();
    await flush();

    await flush(29_999);
    expect(arrivalCalls()).toBe(1);
    await flush(1);
    expect(arrivalCalls()).toBe(2);
  });

  it('[passenger_stop_view.AC-12] stops refreshing while the tab is hidden and refreshes at once when visible again', async () => {
    const { arrivalCalls } = api();
    renderStop();
    await flush();
    expect(arrivalCalls()).toBe(1);

    act(() => setVisibility('hidden'));
    await flush(120_000);
    expect(arrivalCalls()).toBe(1);

    act(() => setVisibility('visible'));
    await flush();
    expect(arrivalCalls()).toBe(2);
    // And the periodic refresh resumes.
    await flush(20_000);
    expect(arrivalCalls()).toBe(3);
  });

  it('[passenger_stop_view.AC-13] counts the minutes down every 15 s using the server time, not the device clock', async () => {
    // The device clock is 2 minutes ahead of the server.
    vi.setSystemTime(GENERATED_AT + 120_000);
    const data = ARRIVALS_REALTIME();
    data.refresh_after_s = 30;
    data.arrivals = [{ ...data.arrivals[1]!, minutes: 4, arrival_at: '2026-11-04T07:43:10Z' }];
    arrivalsReply = () => ok(data);
    api();
    renderStop();
    await flush();

    const [item] = arrivalItems();
    expect(spokenText(item!)).toContain('llega en 4 minutos');
    expect(item).toHaveTextContent('4 min');

    await flush(14_999);
    expect(spokenText(arrivalItems()[0]!)).toContain('llega en 4 minutos');

    await flush(1);
    expect(spokenText(arrivalItems()[0]!)).toContain('llega en 3 minutos');
    expect(arrivalItems()[0]).toHaveTextContent('3 min');
  });

  it('[passenger_stop_view.AC-14] shows the update time and refreshes on demand announcing "Datos actualizados"', async () => {
    const { arrivalCalls } = api();
    renderStop();
    await flush();

    // generated_at 07:40:00Z is 08:40:00 in València.
    expect(screen.getByText('Actualizado a las 08:40:00')).toBeInTheDocument();
    expect(politeRegion()).toHaveTextContent('');

    const pending = deferred<FakeReply>();
    arrivalsReply = () => pending.promise;
    fireEvent.click(screen.getByRole('button', { name: 'Actualizar' }));
    await flush();
    expect(arrivalCalls()).toBe(2);
    await flush(100);
    expect(politeRegion()).toHaveTextContent('');

    pending.resolve(ok({ ...ARRIVALS_REALTIME(), generated_at: '2026-11-04T07:40:07Z' }));
    await flush(100);
    expect(politeRegion()).toHaveTextContent('Datos actualizados');
    expect(screen.getByText('Actualizado a las 08:40:07')).toBeInTheDocument();
  });

  it('[passenger_stop_view.AC-15] announces once when an automatic refresh brings the first 93 at 0 minutes', async () => {
    api();
    renderStop();
    await flush();
    expect(politeRegion()).toHaveTextContent('');

    const next = ARRIVALS_REALTIME();
    next.generated_at = '2026-11-04T07:40:20Z';
    next.arrivals[1] = { ...next.arrivals[1]!, minutes: 0, arrival_at: '2026-11-04T07:40:20Z' };
    arrivalsReply = () => ok(next);
    await flush(20_000);
    await flush(100);
    expect(politeRegion()).toHaveTextContent(
      'Línea 93 hacia Passeig Marítim - Hospital Malva-rosa está llegando',
    );

    // Following refreshes do not repeat it.
    politeRegion().textContent = '';
    await flush(20_000);
    await flush(100);
    expect(politeRegion()).toHaveTextContent('');
  });

  it('[passenger_stop_view.AC-14] [passenger_stop_view.AC-15] does not announce automatic refreshes', async () => {
    api();
    renderStop();
    await flush();

    await flush(20_000);
    await flush(100);

    expect(politeRegion()).toHaveTextContent('');
  });
});
