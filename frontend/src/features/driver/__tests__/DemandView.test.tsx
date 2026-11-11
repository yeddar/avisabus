import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FakeWebSocket } from '../../../test/FakeWebSocket';
import { mockApi } from '../../../test/mockApi';
import { renderWithProviders } from '../../../test/render';
import { DemandView, type DemandViewProps } from '../DemandView';
import { getDriverToken, setDriverToken } from '../session';
import type { DriverView } from '../types';
import { useDriverShift } from '../useDriverShift';
import { driverView, SERVICE, stopDemand } from './fixtures';

function Demand(props: Omit<DemandViewProps, 'service' | 'shift'>) {
  const shift = useDriverShift(true, vi.fn());
  return <DemandView service={SERVICE} shift={shift} {...props} />;
}

function renderDemand(initialView: DriverView | null = driverView()) {
  const onNextDeparture = vi.fn();
  const onSessionEnd = vi.fn();
  const result = renderWithProviders(
    <MemoryRouter>
      <Demand
        initialView={initialView}
        onNextDeparture={onNextDeparture}
        onSessionEnd={onSessionEnd}
      />
    </MemoryRouter>,
  );
  return { onNextDeparture, onSessionEnd, ...result };
}

function receiveView(view: DriverView) {
  act(() => {
    const socket = FakeWebSocket.last();
    if (socket.readyState === FakeWebSocket.CONNECTING) socket.open();
    socket.receive({ type: 'driver.view', ...view });
  });
}

const FIVE_STOPS = ['A', 'B', 'C', 'D', 'E'].map((name, index) =>
  stopDemand({ stop_id: String(index), name: `Parada ${name}`, distance_m: 100 * (index + 1) }),
);

describe('DemandView', () => {
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
    setDriverToken('token-1');
    FakeWebSocket.reset();
    Object.defineProperty(navigator, 'geolocation', {
      configurable: true,
      value: { watchPosition: vi.fn(() => 1), clearWatch: vi.fn(), getCurrentPosition: vi.fn() },
    });
    mockApi(() => ({ status: 204, body: null }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    Object.defineProperty(navigator, 'geolocation', { configurable: true, value: undefined });
  });

  it('[driver_ui.AC-05] shows the line and destination of the departure before any view arrives', () => {
    renderDemand(null);

    const heading = screen.getByRole('heading', { level: 1 });
    expect(heading).toHaveTextContent('93');
    expect(heading).toHaveTextContent('hacia Passeig Marítim - Hospital Malva-rosa');
    expect(screen.getByText('Salida a las 08:40')).toBeInTheDocument();
    expect(screen.queryByRole('list')).not.toBeInTheDocument();
  });

  it('[driver_ui.AC-05] shows the first 3 stops in large cards and the next 2 in small ones', () => {
    renderDemand(driverView({ stops: FIVE_STOPS }));

    const lists = screen.getAllByRole('list');
    expect(within(lists[0] as HTMLElement).getAllByRole('listitem')).toHaveLength(3);
    expect(within(lists[1] as HTMLElement).getAllByRole('listitem')).toHaveLength(2);
    expect(within(lists[0] as HTMLElement).getByText('Parada A')).toBeInTheDocument();
    expect(within(lists[1] as HTMLElement).getByText('Parada D')).toBeInTheDocument();
    expect(within(lists[1] as HTMLElement).getByText('400 m')).toBeInTheDocument();
  });

  it('[driver_ui.AC-05] each stop shows name, distance, people waiting and needs with icon and text', () => {
    const { container } = renderDemand(
      driverView({
        total_waiting: 2,
        stops: [
          stopDemand({
            name: 'Parada A',
            distance_m: 640,
            waiting: 2,
            needs: { RAMP: 1, EXTRA_TIME: 1, SEAT: 1, VISUAL: 1 },
            alert_ids: ['a1', 'a2'],
          }),
        ],
      }),
    );

    const card = screen.getAllByRole('listitem')[0] as HTMLElement;
    expect(card).toHaveTextContent('Parada A');
    expect(card).toHaveTextContent('640 m');
    expect(card).toHaveTextContent('2 personas esperando');
    expect(card).toHaveTextContent('1 rampa');
    expect(card).toHaveTextContent('1 más tiempo');
    expect(card).toHaveTextContent('1 asiento');
    expect(card).toHaveTextContent('1 visión');
    expect(container.querySelectorAll('li svg')).toHaveLength(4);
    expect(screen.queryByText('Sin solicitudes en las próximas paradas')).not.toBeInTheDocument();
  });

  it('[driver_ui.AC-05] uses the singular for one person and hides the needs without requests', () => {
    renderDemand(
      driverView({
        total_waiting: 1,
        stops: [stopDemand({ waiting: 1, alert_ids: ['a1'] })],
      }),
    );

    const card = screen.getByRole('listitem');
    expect(card).toHaveTextContent('1 persona esperando');
    expect(card).not.toHaveTextContent('rampa');
  });

  it('[driver_ui.AC-05] with nobody waiting at any stop says "Sin solicitudes en las próximas paradas"', () => {
    renderDemand(driverView({ stops: FIVE_STOPS }));

    expect(screen.getByText('Sin solicitudes en las próximas paradas')).toBeInTheDocument();
    const zero = screen
      .getAllByRole('listitem')
      .filter((item) => item.textContent?.includes('0 personas esperando'));
    expect(zero).toHaveLength(5);
  });

  it('[driver_ui.AC-06] shows the free places and seats, or that the occupancy is not available', () => {
    renderDemand(driverView({ free_places: 30, free_seats: 4 }));
    expect(screen.getByText('30 plazas libres · 4 asientos')).toBeInTheDocument();

    receiveView(driverView({ free_places: null, free_seats: null }));

    expect(screen.getByText('Ocupación no disponible')).toBeInTheDocument();
  });

  it('[driver_ui.AC-06] shows the capacity strip when the view has capacity_alert', () => {
    renderDemand(driverView({ capacity_alert: true, total_waiting: 35, free_places: 30 }));

    expect(screen.getByText('Esperan 35 personas y quedan 30 plazas')).toBeInTheDocument();
  });

  it('[driver_ui.AC-08] keeps the last list while the position is stale', () => {
    renderDemand(driverView({ stops: FIVE_STOPS }));

    receiveView(driverView({ gps: 'STALE', stops: FIVE_STOPS }));

    expect(screen.getByText('Posición desactualizada')).toBeVisible();
    expect(screen.getByText('Parada A')).toBeInTheDocument();
  });

  it('[driver_ui.AC-08] "Elegir la siguiente salida" asks for the next departure', () => {
    const { onNextDeparture } = renderDemand(driverView({ finished: true }));

    fireEvent.click(screen.getByRole('button', { name: 'Elegir la siguiente salida' }));

    expect(onNextDeparture).toHaveBeenCalledTimes(1);
  });

  it('[driver_ui.AC-10] after confirming it calls DELETE, forgets the token and ends with ENDED', async () => {
    const api = mockApi(() => ({ status: 204, body: null }));
    const { onSessionEnd } = renderDemand();

    fireEvent.click(screen.getByRole('button', { name: 'Finalizar turno' }));
    expect(screen.getByRole('dialog', { name: '¿Finalizar el turno?' })).toBeInTheDocument();
    expect(api.calls('/driver/sessions/current')).toBe(0);

    fireEvent.click(screen.getByRole('button', { name: 'Finalizar' }));

    await waitFor(() => expect(onSessionEnd).toHaveBeenCalledWith('ENDED'));
    const call = api.fetchMock.mock.calls.find(([, init]) => init?.method === 'DELETE');
    expect(String(call?.[0])).toBe('/api/v1/driver/sessions/current');
    expect(getDriverToken()).toBeNull();
  });

  it('[driver_ui.AC-10] "Seguir" keeps the shift open', () => {
    const { onSessionEnd } = renderDemand();

    fireEvent.click(screen.getByRole('button', { name: 'Finalizar turno' }));
    fireEvent.click(screen.getByRole('button', { name: 'Seguir' }));

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(onSessionEnd).not.toHaveBeenCalled();
  });
});
