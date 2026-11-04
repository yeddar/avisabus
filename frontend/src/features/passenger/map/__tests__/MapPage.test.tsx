import { act, fireEvent, screen, within } from '@testing-library/react';
import { RouterProvider, createMemoryRouter } from 'react-router-dom';
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';

import { routes } from '../../../../app/routes';
import type { Language } from '../../../../shared/i18n/languages';
import {
  POSITION_EN_ROUTE,
  POSITION_NO_ARRIVAL,
  POSITION_NOT_STARTED,
  SHAPE_93,
} from '../../../../test/fixtures/api';
import {
  NETWORK_UNAVAILABLE,
  NetworkFailure,
  STOP_NOT_FOUND,
  deferred,
  mockApi,
  ok,
  problem,
  setVisibility,
  type FakeReply,
} from '../../../../test/mockApi';
import { renderWithProviders } from '../../../../test/render';
import type { BusMapProps } from '../BusMap';

/** Leaflet is tested in BusMap.test.tsx: here the map only records what it receives. */
const mapProps = vi.hoisted(() => ({ last: null as BusMapProps | null }));
vi.mock('../BusMap', () => ({
  BusMap: (props: BusMapProps) => {
    mapProps.last = props;
    return <div data-testid="bus-map" />;
  },
}));

const TOKEN = 'AbCdEfGhIjKlMnOpQrStUv';
const MAP_URL = `/p/508/map/93/0?t=${TOKEN}`;
const GENERATED_AT = Date.parse('2026-11-04T07:40:00Z');
const RETRIES_MS = 3_100;
const LINE_NOT_AT_STOP = 'https://avisabus/problems/line-not-at-stop';
const DESTINATION = 'Passeig Marítim - Hospital Malva-rosa';

type Reply = () => FakeReply | Promise<FakeReply>;

function renderMap(path = MAP_URL, language: Language = 'es') {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  return { ...renderWithProviders(<RouterProvider router={router} />, { language }), router };
}

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

function summaryText(): string {
  const region = screen.getByRole('region', { name: 'Dónde está el autobús' });
  return within(region).getByText(/autobús|Posición/, { selector: 'p' }).textContent ?? '';
}

describe('MapPage', () => {
  let positionReply: Reply;
  let shapeReply: Reply;

  // The first dynamic import takes real time (module transform), which fake timers cannot
  // advance; once loaded, React.lazy still shows the fallback on the first render.
  beforeAll(async () => {
    await import('../MapPage');
  });

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(GENERATED_AT);
    mapProps.last = null;
    positionReply = () => ok(POSITION_EN_ROUTE());
    shapeReply = () => ok(SHAPE_93());
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    setVisibility('visible');
    document.title = '';
  });

  function api() {
    return mockApi((url) => {
      if (url.pathname === '/api/v1/stops/508/lines/93/position') return positionReply();
      if (url.pathname === '/api/v1/shapes/994_488_2271') return shapeReply();
      throw new Error(`unexpected request ${url.pathname}`);
    });
  }

  it('[passenger_map_view.AC-02] shows "Cargando mapa…" as a status while the map chunk loads', async () => {
    api();
    renderMap();

    expect(screen.getByText('Cargando mapa…')).toHaveAttribute('role', 'status');
    await flush();
    expect(screen.queryByText('Cargando mapa…', { selector: '[role="status"]' })).toBeNull();
    expect(screen.getByRole('link', { name: 'Volver a la parada' })).toBeInTheDocument();
  });

  it('[passenger_map_view.AC-03] h1 "Línea {line} hacia {destination}" with the arrival destination, title and back link with the token', async () => {
    const { fetchMock } = api();
    renderMap();
    await flush();

    const h1 = screen.getByRole('heading', { level: 1 });
    expect(h1).toHaveTextContent(`Línea 93 hacia ${DESTINATION}`);
    expect(within(h1).getByText(DESTINATION)).toHaveAttribute('lang', 'ca-ES-valencia');
    expect(document.title).toBe(`Línea 93 hacia ${DESTINATION} · AvisaBus`);
    expect(screen.getByRole('link', { name: 'Volver a la parada' })).toHaveAttribute(
      'href',
      `/p/508?t=${TOKEN}`,
    );
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe(
      `/api/v1/stops/508/lines/93/position?direction_id=0&t=${TOKEN}`,
    );
  });

  it('[passenger_map_view.AC-03] without an arrival the destination is the headsign; in Valencian', async () => {
    positionReply = () => ok({ ...POSITION_NO_ARRIVAL(), headsign: 'Malva-rosa' });
    api();
    renderMap(MAP_URL, 'ca');
    await flush();

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'Línia 93 cap a Malva-rosa',
    );
    expect(document.title).toBe('Línia 93 cap a Malva-rosa · AvisaBus');
    expect(screen.getByRole('link', { name: 'Torna a la parada' })).toHaveAttribute(
      'href',
      `/p/508?t=${TOKEN}`,
    );
  });

  it('[passenger_map_view.AC-04] [passenger_map_view.AC-05] shows the summary and its badge before the map', async () => {
    api();
    renderMap();
    await flush();

    const summary = screen.getByRole('region', { name: 'Dónde está el autobús' });
    const map = screen.getByTestId('bus-map');
    expect(summary.compareDocumentPosition(map) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(summaryText()).toBe(
      'El autobús está a 3,4 km de tu parada, a 3 paradas. Próxima parada: Cid - Hospital General. Llega en 5 minutos.',
    );
    expect(within(summary).getByText('Posición estimada')).toBeVisible();
  });

  it('[passenger_map_view.AC-05] (v1.2) NO_ARRIVAL: no badge next to "Posición no disponible"', async () => {
    positionReply = () => ok(POSITION_NO_ARRIVAL());
    api();
    renderMap();
    await flush();

    const summary = screen.getByRole('region', { name: 'Dónde está el autobús' });
    expect(summaryText()).toBe(
      'Posición no disponible en este momento. No hay llegadas previstas de esta línea en tu parada.',
    );
    expect(within(summary).queryByText('Posición estimada')).toBeNull();
    expect(within(summary).queryByText('Posición según horario')).toBeNull();
  });

  it('[passenger_map_view.AC-04] NOT_STARTED names the first stop once the shape has arrived', async () => {
    positionReply = () => ok(POSITION_NOT_STARTED());
    const shape = deferred<FakeReply>();
    shapeReply = () => shape.promise;
    api();
    renderMap();
    await flush();

    expect(summaryText()).toBe(
      'El autobús aún no ha salido de la primera parada del recorrido. Llega a las 08:58.',
    );
    expect(screen.getByText('Posición según horario')).toBeVisible();

    shape.resolve(ok(SHAPE_93()));
    await flush();
    expect(summaryText()).toBe(
      'El autobús aún no ha salido de Avinguda del Cid. Llega a las 08:58.',
    );
  });

  it('[passenger_map_view.AC-04] counts the minutes down with the server time between refreshes', async () => {
    // The device clock is 2 minutes ahead of the server.
    vi.setSystemTime(GENERATED_AT + 120_000);
    const data = POSITION_EN_ROUTE();
    data.refresh_after_s = 30;
    data.arrival = { ...data.arrival!, minutes: 5, arrival_at: '2026-11-04T07:44:10Z' };
    positionReply = () => ok(data);
    api();
    renderMap();
    await flush();
    expect(summaryText()).toMatch(/Llega en 5 minutos\.$/);

    await flush(15_000); // 07:40:15 at the server: 3 min 55 s left
    expect(summaryText()).toMatch(/Llega en 4 minutos\.$/);
  });

  it('[passenger_map_view.AC-07] passes the shape, the stops and the bus to the map, ready to frame', async () => {
    api();
    renderMap();
    await flush();
    await flush(100); // the shape is asked once the position has arrived

    const props = mapProps.last!;
    expect(props.ready).toBe(true);
    expect(props.model.line.coords).toHaveLength(SHAPE_93().coordinates.length);
    expect(props.model.bus).not.toBeNull();
  });

  it('[passenger_map_view.AC-08] without a position the map waits for the shape before framing', async () => {
    positionReply = () => ok(POSITION_NO_ARRIVAL());
    const shape = deferred<FakeReply>();
    shapeReply = () => shape.promise;
    api();
    renderMap();
    await flush();
    expect(mapProps.last?.ready).toBe(false);

    shape.resolve(ok(SHAPE_93()));
    await flush();
    expect(mapProps.last?.ready).toBe(true);
    expect(mapProps.last?.model.line.coords.length).toBeGreaterThan(0);
  });

  it('[passenger_map_view.AC-12] refreshes the position every min(refresh_after_s, 30) s and asks for the shape once', async () => {
    const { calls } = api();
    renderMap();
    await flush();
    expect(calls('/position')).toBe(1);
    expect(calls('/shapes/')).toBe(1);

    await flush(20_000);
    await flush(20_000);
    await flush(20_000);

    expect(calls('/position')).toBe(4);
    expect(calls('/shapes/')).toBe(1);
  });

  it('[passenger_map_view.AC-12] pauses while hidden and refreshes when visible again', async () => {
    const { calls } = api();
    renderMap();
    await flush();

    act(() => setVisibility('hidden'));
    await flush(120_000);
    expect(calls('/position')).toBe(1);

    act(() => setVisibility('visible'));
    await flush();
    expect(calls('/position')).toBe(2);
  });

  it('[passenger_map_view.AC-06] announces once when a refresh brings the bus to the stop', async () => {
    api();
    renderMap();
    await flush();
    expect(politeRegion()).toHaveTextContent('');

    positionReply = () => ok({ ...POSITION_EN_ROUTE(), status: 'AT_STOP' });
    await flush(20_000);
    await flush(100);
    expect(politeRegion()).toHaveTextContent('El autobús está llegando a tu parada');
  });

  it.each([
    ['line-not-at-stop', LINE_NOT_AT_STOP],
    ['stop-not-found', STOP_NOT_FOUND],
  ])(
    '[passenger_map_view.AC-13] a 404 (%s) shows "No se encuentra esta línea en tu parada" with a link to the stop',
    async (_name, type) => {
      positionReply = () => problem(404, type);
      const { calls } = api();
      renderMap();
      await flush();

      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
        'No se encuentra esta línea en tu parada',
      );
      expect(screen.getByRole('link', { name: 'Volver a la parada' })).toHaveAttribute(
        'href',
        `/p/508?t=${TOKEN}`,
      );
      expect(screen.queryByTestId('bus-map')).toBeNull();
      await flush(60_000);
      expect(calls('/position')).toBe(1);
      expect(calls('/shapes/')).toBe(0);
    },
  );

  it('[passenger_map_view.AC-13] in Valencian', async () => {
    positionReply = () => problem(404, LINE_NOT_AT_STOP);
    api();
    renderMap(MAP_URL, 'ca');
    await flush();

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      'No es troba esta línia en la teua parada',
    );
    expect(document.title).toBe('No es troba esta línia en la teua parada · AvisaBus');
  });

  it.each([
    ['without a token', '/p/508/map/93/0'],
    ['with an empty token', '/p/508/map/93/0?t='],
    ['with a non-numeric direction', `/p/508/map/93/abc?t=${TOKEN}`],
    ['with a negative direction', `/p/508/map/93/-1?t=${TOKEN}`],
    ['with a decimal direction', `/p/508/map/93/1.5?t=${TOKEN}`],
  ])(
    '[passenger_map_view.AC-13] %s: "No se encuentra esta línea en tu parada" without calling the API',
    async (_name, path) => {
      const { fetchMock } = api();
      renderMap(path);
      await flush();

      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
        'No se encuentra esta línea en tu parada',
      );
      expect(fetchMock).not.toHaveBeenCalled();
    },
  );

  it('[passenger_map_view.AC-13] a 503 is retried and then offers "Reintentar"', async () => {
    positionReply = () => problem(503, NETWORK_UNAVAILABLE);
    const { calls } = api();
    renderMap();
    await flush(RETRIES_MS);

    expect(calls('/position')).toBe(3);
    expect(screen.getByText('No se han podido cargar los datos.')).toBeInTheDocument();

    positionReply = () => ok(POSITION_EN_ROUTE());
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
    await flush(100);

    expect(calls('/position')).toBe(4);
    expect(screen.queryByRole('button', { name: 'Reintentar' })).toBeNull();
    expect(summaryText()).toMatch(/^El autobús está a 3,4 km/);
    expect(politeRegion()).toHaveTextContent('Datos actualizados');
  });

  it('[passenger_map_view.AC-13] a network error on a refresh keeps the data, marked as outdated', async () => {
    api();
    renderMap();
    await flush();

    positionReply = () => {
      throw new NetworkFailure();
    };
    await flush(20_000 + RETRIES_MS);

    expect(screen.getByText('Datos de las 08:40, pueden no estar actualizados')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeVisible();
    expect(summaryText()).toMatch(/^El autobús está a 3,4 km/);
    expect(screen.getByTestId('bus-map')).toBeInTheDocument();
    // Automatic refreshes never announce, not even when they fail.
    expect(politeRegion()).toHaveTextContent('');
  });

  it('[passenger_map_view.AC-13] a failed "Reintentar" announces it and keeps the focus on the button', async () => {
    positionReply = () => problem(503, NETWORK_UNAVAILABLE);
    api();
    renderMap();
    await flush(RETRIES_MS);

    const retry = screen.getByRole('button', { name: 'Reintentar' });
    retry.focus();
    fireEvent.click(retry);
    await flush(RETRIES_MS);

    expect(politeRegion()).toHaveTextContent('No se han podido actualizar los datos');
    expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Reintentar' }));
  });

  it('[passenger_map_view.AC-13] a 503 of the shape gets the same treatment: retried, then "Reintentar" asks again', async () => {
    shapeReply = () => problem(503, NETWORK_UNAVAILABLE);
    const { calls } = api();
    renderMap();
    await flush(RETRIES_MS);

    expect(calls('/shapes/')).toBe(3);
    expect(screen.getByText('No se han podido cargar los datos.')).toBeInTheDocument();
    // The position is still shown, and the map without the shape.
    expect(summaryText()).toMatch(/^El autobús está a 3,4 km/);
    expect(mapProps.last?.model.line.coords).toEqual([]);

    shapeReply = () => ok(SHAPE_93());
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
    await flush(100);

    expect(calls('/shapes/')).toBe(4);
    expect(screen.queryByRole('button', { name: 'Reintentar' })).toBeNull();
    expect(mapProps.last?.model.line.coords.length).toBeGreaterThan(0);
  });

  it('[passenger_map_view.AC-07] [passenger_map_view.AC-13] a shape that does not exist is not an error: the map shows the stop and the bus', async () => {
    shapeReply = () => problem(404, 'https://avisabus/problems/shape-not-found');
    const { calls } = api();
    renderMap();
    await flush(RETRIES_MS);

    expect(calls('/shapes/')).toBe(1);
    expect(screen.queryByRole('button', { name: 'Reintentar' })).toBeNull();
    expect(mapProps.last?.ready).toBe(true);
    expect(mapProps.last?.model.line.coords).toEqual([]);
    expect(mapProps.last?.model.stops.map((stop) => stop.id)).toEqual(['508']);
  });

  it('[passenger_map_view.AC-07] without shape_id the map shows the stop and the shape is not asked', async () => {
    positionReply = () => ok({ ...POSITION_NO_ARRIVAL(), shape_id: null });
    const { calls } = api();
    renderMap();
    await flush();

    expect(calls('/shapes/')).toBe(0);
    expect(mapProps.last?.ready).toBe(true);
    expect(mapProps.last?.model.stops).toHaveLength(1);
  });
});
