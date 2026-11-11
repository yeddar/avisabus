import { act, fireEvent, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FakeWebSocket } from '../../../test/FakeWebSocket';
import { mockApi } from '../../../test/mockApi';
import { renderWithProviders } from '../../../test/render';
import { DemandView } from '../DemandView';
import { setDriverToken } from '../session';
import { playTone } from '../tone';
import type { DriverView } from '../types';
import { useDriverShift } from '../useDriverShift';
import { driverView, SERVICE, stopDemand } from './fixtures';

vi.mock('../tone', () => ({ playTone: vi.fn(), resetToneForTests: vi.fn() }));

const NEW_LABEL = 'Nueva';

function viewWith(alertIds: string[], overrides: Partial<DriverView> = {}): DriverView {
  return driverView({
    total_waiting: alertIds.length,
    stops: [stopDemand({ name: 'Parada A', waiting: alertIds.length, alert_ids: alertIds })],
    ...overrides,
  });
}

function Demand({ initialView }: { initialView: DriverView | null }) {
  const shift = useDriverShift(true, vi.fn());
  return (
    <DemandView
      service={SERVICE}
      initialView={initialView}
      shift={shift}
      onNextDeparture={vi.fn()}
      onSessionEnd={vi.fn()}
    />
  );
}

function renderDemand(initialView: DriverView | null = null) {
  return renderWithProviders(
    <MemoryRouter>
      <Demand initialView={initialView} />
    </MemoryRouter>,
  );
}

function receiveView(view: DriverView) {
  act(() => {
    const socket = FakeWebSocket.last();
    if (socket.readyState === FakeWebSocket.CONNECTING) socket.open();
    socket.receive({ type: 'driver.view', ...view });
  });
}

describe('DemandView tone and highlight', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.mocked(playTone).mockClear();
    sessionStorage.clear();
    localStorage.clear();
    setDriverToken('token-1');
    FakeWebSocket.reset();
    vi.spyOn(Math, 'random').mockReturnValue(0.5);
    Object.defineProperty(navigator, 'geolocation', {
      configurable: true,
      value: { watchPosition: vi.fn(() => 1), clearWatch: vi.fn(), getCurrentPosition: vi.fn() },
    });
    mockApi(() => ({ status: 204, body: null }));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    Object.defineProperty(navigator, 'geolocation', { configurable: true, value: undefined });
  });

  it('[driver_ui.AC-07] the first view does not sound or highlight', () => {
    renderDemand();

    receiveView(viewWith(['a']));

    expect(playTone).not.toHaveBeenCalled();
    expect(screen.queryByText(NEW_LABEL)).not.toBeInTheDocument();
  });

  it('[driver_ui.AC-07] a new alert_id plays the tone and highlights its stop for 10 s', () => {
    renderDemand();
    receiveView(viewWith(['a']));

    receiveView(viewWith(['a', 'b']));

    expect(playTone).toHaveBeenCalledTimes(1);
    expect(screen.getByText(NEW_LABEL)).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(9_999);
    });
    expect(screen.getByText(NEW_LABEL)).toBeInTheDocument();

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(screen.queryByText(NEW_LABEL)).not.toBeInTheDocument();
  });

  it('[driver_ui.AC-07] a view without new requests does not sound again', () => {
    renderDemand();
    receiveView(viewWith(['a']));
    receiveView(viewWith(['a', 'b']));
    vi.mocked(playTone).mockClear();

    receiveView(viewWith(['a', 'b']));

    expect(playTone).not.toHaveBeenCalled();
  });

  it('[driver_ui.AC-07] the first view after reconnecting marks its requests as seen without a tone', () => {
    renderDemand();
    receiveView(viewWith(['a']));

    act(() => FakeWebSocket.last().serverClose(1006));
    act(() => {
      vi.advanceTimersByTime(1_000);
    });
    receiveView(viewWith(['a', 'b']));

    expect(playTone).not.toHaveBeenCalled();

    receiveView(viewWith(['a', 'b', 'c']));

    expect(playTone).toHaveBeenCalledTimes(1);
  });

  it('[driver_ui.AC-07] [driver_ui.AC-09] right after choosing the departure it asks for the view once and marks it as seen', async () => {
    const api = mockApi(() => ({ status: 200, body: viewWith(['a']) }));
    renderDemand();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(api.calls('/current/view')).toBe(1);
    expect(screen.getByText('Parada A')).toBeInTheDocument();
    expect(playTone).not.toHaveBeenCalled();
    expect(screen.queryByText(NEW_LABEL)).not.toBeInTheDocument();
  });

  it('[driver_ui.AC-07] an initial view from the first load also counts as seen', () => {
    renderDemand(viewWith(['a']));

    receiveView(viewWith(['a']));
    receiveView(viewWith(['a']));

    expect(playTone).not.toHaveBeenCalled();
  });

  it('[driver_ui.AC-07] silenced, it highlights without a tone and remembers the choice in the device', () => {
    renderDemand();
    receiveView(viewWith(['a']));

    fireEvent.click(screen.getByRole('button', { name: 'Silenciar tono' }));

    expect(localStorage.getItem('avisabus.driverMute')).toBe('true');
    expect(screen.getByRole('button', { name: 'Activar tono' })).toBeInTheDocument();

    receiveView(viewWith(['a', 'b']));

    expect(playTone).not.toHaveBeenCalled();
    expect(screen.getByText(NEW_LABEL)).toBeInTheDocument();
  });

  it('[driver_ui.AC-07] starts silenced when the device remembers it, and can be activated again', () => {
    localStorage.setItem('avisabus.driverMute', 'true');
    renderDemand();
    receiveView(viewWith(['a']));

    fireEvent.click(screen.getByRole('button', { name: 'Activar tono' }));
    expect(localStorage.getItem('avisabus.driverMute')).toBe('false');

    receiveView(viewWith(['a', 'b']));

    expect(playTone).toHaveBeenCalledTimes(1);
  });
});
