import { fireEvent, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { mockApi, NetworkFailure, ok, problem } from '../../../test/mockApi';
import { renderWithProviders } from '../../../test/render';
import { ServicePicker } from '../ServicePicker';
import { setDriverToken } from '../session';
import { DEPARTURE_FREE, DEPARTURE_TAKEN, LINE_93 } from './fixtures';

type Reply = ReturnType<typeof ok> | ReturnType<typeof problem>;

function apiWith(put: () => Reply = () => ok({})) {
  return mockApi((url) => {
    if (url.pathname === '/api/v1/driver/lines') return ok({ lines: [LINE_93] });
    if (url.pathname === '/api/v1/driver/departures')
      return ok({ departures: [DEPARTURE_FREE, DEPARTURE_TAKEN] });
    if (url.pathname === '/api/v1/driver/sessions/current/service') return put();
    return problem(500, 'unexpected');
  });
}

function renderPicker(onExit = vi.fn(), onSelected = vi.fn(), language: 'es' | 'ca' = 'es') {
  renderWithProviders(
    <MemoryRouter>
      <ServicePicker onSelected={onSelected} onExit={onExit} />
    </MemoryRouter>,
    { language },
  );
  return { onExit, onSelected };
}

/** Lines and departures in sequence: each call takes the next reply (the last one repeats). */
function apiReplying(lines: (() => Reply)[], departures: (() => Reply)[], put = () => ok({})) {
  const next = (replies: (() => Reply)[]) => {
    const reply = replies.length > 1 ? replies.shift() : replies[0];
    return (reply as () => Reply)();
  };
  return mockApi((url) => {
    if (url.pathname === '/api/v1/driver/lines') return next(lines);
    if (url.pathname === '/api/v1/driver/departures') return next(departures);
    if (url.pathname === '/api/v1/driver/sessions/current/service') return put();
    return problem(500, 'unexpected');
  });
}

const LINES = () => ok({ lines: [LINE_93] });
const DEPARTURES = () => ok({ departures: [DEPARTURE_FREE, DEPARTURE_TAKEN] });
const NO_DEPARTURES = () => ok({ departures: [] });
const SERVER_ERROR = () => problem(503, 'unavailable');
const NETWORK_ERROR = (): Reply => {
  throw new NetworkFailure();
};

async function pickLine() {
  fireEvent.click(await screen.findByRole('button', { name: 'Línea 93' }));
}

async function pickDirection() {
  fireEvent.click(
    await screen.findByRole('button', { name: 'Passeig Marítim - Hospital Malva-rosa' }),
  );
}

async function departures() {
  await pickLine();
  await pickDirection();
  await screen.findByRole('heading', { level: 1, name: 'Elige la salida' });
}

describe('ServicePicker', () => {
  beforeEach(() => {
    sessionStorage.clear();
    setDriverToken('token-1');
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('[driver_ui.AC-02] shows the lines as buttons with the accessible line colour', async () => {
    apiWith();
    renderPicker();

    const button = await screen.findByRole('button', { name: 'Línea 93' });
    expect(button).toHaveStyle({ backgroundColor: '#e50000', color: '#ffffff' });
    expect(button).toHaveTextContent('93');
  });

  it('[driver_ui.AC-02] offers the two directions by headsign and "Volver" returns to the lines', async () => {
    apiWith();
    renderPicker();
    await pickLine();

    await screen.findByRole('heading', { level: 1, name: 'Elige el sentido' });
    expect(screen.getByRole('button', { name: 'Av. del Cid' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Volver' }));

    await screen.findByRole('heading', { level: 1, name: 'Elige la línea' });
  });

  it('[driver_ui.AC-02] lists hour, first stop and destination; taken departures are disabled with "Ya en servicio"', async () => {
    const api = apiWith();
    renderPicker();
    await departures();

    const free = await screen.findByRole('button', { name: /08:40/ });
    expect(free).toHaveTextContent('Hospital Malva-rosa');
    expect(free).toHaveTextContent('Passeig Marítim - Hospital Malva-rosa');
    expect(free).toBeEnabled();
    const taken = screen.getByRole('button', { name: /08:55/ });
    expect(taken).toBeDisabled();
    expect(taken).toHaveTextContent('Ya en servicio');
    const departuresCall = api.fetchMock.mock.calls
      .map(([input]) => String(input))
      .find((url) => url.includes('/driver/departures'));
    expect(departuresCall).toBe('/api/v1/driver/departures?line=93&direction_id=0');
  });

  it('[driver_ui.AC-02] "Volver" in the departures step returns to the directions, and in the lines step leaves the picker', async () => {
    apiWith();
    const { onExit } = renderPicker();
    await departures();

    fireEvent.click(screen.getByRole('button', { name: 'Volver' }));
    await screen.findByRole('heading', { level: 1, name: 'Elige el sentido' });
    fireEvent.click(screen.getByRole('button', { name: 'Volver' }));
    await screen.findByRole('heading', { level: 1, name: 'Elige la línea' });

    expect(onExit).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Volver' }));

    expect(onExit).toHaveBeenCalledTimes(1);
  });

  it('[driver_ui.AC-02] choosing a departure calls PUT service and reports the service with the line colours', async () => {
    const api = apiWith();
    const { onSelected } = renderPicker();
    await departures();

    fireEvent.click(await screen.findByRole('button', { name: /08:40/ }));

    await waitFor(() => expect(onSelected).toHaveBeenCalledTimes(1));
    const putCall = api.fetchMock.mock.calls.find(([input]) =>
      String(input).includes('/current/service'),
    );
    expect(putCall?.[1]?.method).toBe('PUT');
    expect(JSON.parse(String(putCall?.[1]?.body))).toEqual({
      line: '93',
      direction_id: 0,
      trip_id: '12345',
      service_date: '2026-11-09',
    });
    expect(onSelected).toHaveBeenCalledWith({
      line: '93',
      direction_id: 0,
      headsign: 'Passeig Marítim - Hospital Malva-rosa',
      trip_id: '12345',
      service_date: '2026-11-09',
      departure_at: '2026-11-09T07:40:00Z',
      color: 'FE0000',
      text_color: 'FFFFFF',
    });
  });

  it('[driver_ui.AC-02] with a 409 refreshes the list and announces "Esa salida ya la lleva otro conductor"', async () => {
    const api = apiWith(() => problem(409, 'departure-taken'));
    const { onSelected } = renderPicker();
    await departures();

    fireEvent.click(await screen.findByRole('button', { name: /08:40/ }));

    await screen.findByText('Esa salida ya la lleva otro conductor', {
      selector: ':not([role="status"])',
    });
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent(/ya la lleva/));
    await waitFor(() => expect(api.calls('/driver/departures')).toBeGreaterThanOrEqual(2));
    expect(onSelected).not.toHaveBeenCalled();
  });

  it('[driver_ui.AC-02] without departures in the window says so, with "Volver" and "Actualizar"', async () => {
    const api = apiReplying([LINES], [NO_DEPARTURES, DEPARTURES]);
    renderPicker();
    await departures();

    expect(
      await screen.findByText('No hay salidas de esta línea y sentido en la próxima hora'),
    ).toBeVisible();
    expect(screen.getByRole('button', { name: 'Volver' })).toBeInTheDocument();
    expect(api.calls('/driver/departures')).toBe(1);

    fireEvent.click(screen.getByRole('button', { name: 'Actualizar' }));

    expect(await screen.findByRole('button', { name: /08:40/ })).toBeEnabled();
    expect(api.calls('/driver/departures')).toBe(2);
    expect(
      screen.queryByText('No hay salidas de esta línea y sentido en la próxima hora'),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Actualizar' })).not.toBeInTheDocument();
  });

  it('[driver_ui.AC-02] a 5xx loading the lines says "No se han podido cargar los datos" and "Reintentar" loads them', async () => {
    const api = apiReplying([SERVER_ERROR, LINES], [DEPARTURES]);
    renderPicker();

    expect(await screen.findByText('No se han podido cargar los datos')).toBeVisible();
    expect(screen.queryByText(/Comprueba la conexión/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Volver' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));

    expect(await screen.findByRole('button', { name: 'Línea 93' })).toBeInTheDocument();
    expect(api.calls('/driver/lines')).toBe(2);
    expect(screen.queryByText('No se han podido cargar los datos')).not.toBeInTheDocument();
  });

  it('[driver_ui.AC-02] a network error loading the departures says "No se han podido cargar los datos" and "Reintentar" loads them', async () => {
    const api = apiReplying([LINES], [NETWORK_ERROR, DEPARTURES]);
    renderPicker();
    await departures();

    expect(await screen.findByText('No se han podido cargar los datos')).toBeVisible();

    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));

    expect(await screen.findByRole('button', { name: /08:40/ })).toBeEnabled();
    expect(api.calls('/driver/departures')).toBe(2);
    expect(screen.queryByText('No se han podido cargar los datos')).not.toBeInTheDocument();
  });

  it('[driver_ui.AC-02] a 5xx or a network error choosing the departure says "No se han podido cargar los datos" with "Reintentar"', async () => {
    const replies: (() => Reply)[] = [SERVER_ERROR, NETWORK_ERROR];
    const api = apiReplying([LINES], [DEPARTURES], () => (replies.shift() ?? SERVER_ERROR)());
    const { onSelected } = renderPicker();
    await departures();

    fireEvent.click(await screen.findByRole('button', { name: /08:40/ }));
    expect(await screen.findByText('No se han podido cargar los datos')).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
    await waitFor(() =>
      expect(screen.queryByText('No se han podido cargar los datos')).not.toBeInTheDocument(),
    );
    await waitFor(() => expect(api.calls('/driver/departures')).toBeGreaterThanOrEqual(3));

    fireEvent.click(await screen.findByRole('button', { name: /08:40/ }));
    expect(await screen.findByText('No se han podido cargar los datos')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Reintentar' })).toBeInTheDocument();
    expect(onSelected).not.toHaveBeenCalled();
  });

  it('[driver_ui.AC-02] shows the texts without departures and of error in Valencian', async () => {
    apiReplying([SERVER_ERROR, LINES], [NO_DEPARTURES]);
    renderPicker(vi.fn(), vi.fn(), 'ca');

    expect(await screen.findByText("No s'han pogut carregar les dades")).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Reintenta' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Línia 93' }));
    fireEvent.click(
      await screen.findByRole('button', { name: 'Passeig Marítim - Hospital Malva-rosa' }),
    );

    expect(
      await screen.findByText("No hi ha eixides d'esta línia i sentit en la pròxima hora"),
    ).toBeVisible();
    expect(screen.getByRole('button', { name: 'Actualitza' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Torna' })).toBeInTheDocument();
  });

  it('[driver_ui.AC-08] starts in the departures step with the same line and direction', async () => {
    apiWith();
    renderWithProviders(
      <MemoryRouter>
        <ServicePicker
          initialChoice={{ line: '93', directionId: 0 }}
          onSelected={vi.fn()}
          onExit={vi.fn()}
        />
      </MemoryRouter>,
    );

    await screen.findByRole('heading', { level: 1, name: 'Elige la salida' });
    expect(await screen.findByRole('button', { name: /08:40/ })).toBeInTheDocument();
  });
});
