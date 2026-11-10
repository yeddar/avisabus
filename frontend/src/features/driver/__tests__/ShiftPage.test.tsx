import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FakeWebSocket } from '../../../test/FakeWebSocket';
import { mockApi, ok, problem } from '../../../test/mockApi';
import { renderWithProviders } from '../../../test/render';
import { setDriverToken } from '../session';
import { ShiftPage } from '../ShiftPage';
import { DEPARTURE_FREE, driverView, LINE_93 } from './fixtures';

function LoginProbe() {
  const { pathname, state } = useLocation();
  const reason = (state as { closedReason?: string } | null)?.closedReason ?? 'none';
  return (
    <p>
      at {pathname} ({reason})
    </p>
  );
}

function renderShift() {
  return renderWithProviders(
    <MemoryRouter initialEntries={['/driver/shift']}>
      <Routes>
        <Route path="/driver" element={<LoginProbe />} />
        <Route path="/driver/shift" element={<ShiftPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('ShiftPage', () => {
  beforeEach(() => {
    sessionStorage.clear();
    FakeWebSocket.reset();
    Object.defineProperty(navigator, 'geolocation', {
      configurable: true,
      value: { watchPosition: vi.fn(() => 1), clearWatch: vi.fn() },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    Object.defineProperty(navigator, 'geolocation', { configurable: true, value: undefined });
  });

  it('[driver_ui.AC-03] without a token it goes back to /driver without calling the API', async () => {
    const api = mockApi(() => ok({}));
    renderShift();

    expect(await screen.findByText(/^at \/driver /)).toBeInTheDocument();
    expect(api.fetchMock).not.toHaveBeenCalled();
  });

  it('[driver_ui.AC-03] a 401 from the current view goes back to /driver and forgets the token', async () => {
    setDriverToken('expired');
    mockApi(() => problem(401, 'invalid-session'));
    renderShift();

    expect(await screen.findByText(/^at \/driver /)).toBeInTheDocument();
    expect(sessionStorage.getItem('avisabus.driverSession')).toBeNull();
  });

  it('[driver_ui.AC-02] without a departure it shows the picker', async () => {
    setDriverToken('token-1');
    mockApi((url) => {
      if (url.pathname.endsWith('/current/view')) return ok(driverView({ service: null }));
      if (url.pathname.endsWith('/driver/lines')) return ok({ lines: [LINE_93] });
      return problem(500, 'unexpected');
    });
    renderShift();

    await screen.findByRole('heading', { level: 1, name: 'Elige la línea' });
  });

  it('[driver_ui.AC-03] a 401 while choosing goes back to /driver', async () => {
    setDriverToken('token-1');
    mockApi((url) => {
      if (url.pathname.endsWith('/current/view')) return ok(driverView({ service: null }));
      return problem(401, 'invalid-session');
    });
    renderShift();

    await waitFor(() => expect(screen.getByText(/^at \/driver /)).toBeInTheDocument());
  });

  it('[driver_ui.AC-05] with a departure already chosen it shows the demand view', async () => {
    setDriverToken('token-1');
    mockApi(() => ok(driverView()));
    renderShift();

    await screen.findByText('Salida a las 08:40');
    expect(screen.getByRole('button', { name: 'Finalizar turno' })).toBeInTheDocument();
  });

  it('[driver_ui.AC-02] after choosing the departure it shows the demand view with that departure', async () => {
    setDriverToken('token-1');
    mockApi((url) => {
      if (url.pathname.endsWith('/current/view')) return ok(driverView({ service: null }));
      if (url.pathname.endsWith('/driver/lines')) return ok({ lines: [LINE_93] });
      if (url.pathname.endsWith('/driver/departures')) return ok({ departures: [DEPARTURE_FREE] });
      if (url.pathname.endsWith('/current/service')) return ok({});
      return { status: 204, body: null };
    });
    renderShift();

    fireEvent.click(await screen.findByRole('button', { name: 'Línea 93' }));
    fireEvent.click(
      await screen.findByRole('button', { name: 'Passeig Marítim - Hospital Malva-rosa' }),
    );
    fireEvent.click(await screen.findByRole('button', { name: /08:40/ }));

    await screen.findByText('Salida a las 08:40');
  });

  it('[driver_ui.AC-08] "Elegir la siguiente salida" returns to the departures of the same line and direction', async () => {
    setDriverToken('token-1');
    mockApi((url) => {
      if (url.pathname.endsWith('/current/view')) return ok(driverView({ finished: true }));
      if (url.pathname.endsWith('/driver/lines')) return ok({ lines: [LINE_93] });
      if (url.pathname.endsWith('/driver/departures')) return ok({ departures: [DEPARTURE_FREE] });
      return { status: 204, body: null };
    });
    renderShift();

    fireEvent.click(await screen.findByRole('button', { name: 'Elegir la siguiente salida' }));

    await screen.findByRole('heading', { level: 1, name: 'Elige la salida' });
    expect(await screen.findByRole('button', { name: /08:40/ })).toBeInTheDocument();
  });

  it('[driver_ui.AC-10] when the server closes the shift it returns to /driver with the reason', async () => {
    setDriverToken('token-1');
    mockApi(() => ok(driverView()));
    renderShift();
    await screen.findByText('Salida a las 08:40');

    act(() => {
      FakeWebSocket.last().open();
      FakeWebSocket.last().receive({ type: 'session.closed', reason: 'IDLE' });
    });

    expect(await screen.findByText('at /driver (IDLE)')).toBeInTheDocument();
    expect(sessionStorage.getItem('avisabus.driverSession')).toBeNull();
  });

  it('[driver_ui.AC-03] the close 4401 of the socket returns to /driver', async () => {
    setDriverToken('token-1');
    mockApi(() => ok(driverView()));
    renderShift();
    await screen.findByText('Salida a las 08:40');

    act(() => FakeWebSocket.last().serverClose(4401));

    expect(await screen.findByText(/^at \/driver /)).toBeInTheDocument();
  });
});
