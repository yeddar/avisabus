import { act, screen } from '@testing-library/react';
import { useRef } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { getDeviceId } from '../../../../shared/device/deviceId';
import { FakeWebSocket } from '../../../../test/FakeWebSocket';
import { alert70, alertFixture } from '../../../../test/fixtures/alerts';
import { mockApi, ok, type FakeReply } from '../../../../test/mockApi';
import { renderWithProviders } from '../../../../test/render';
import { AlertsProvider, FALLBACK_POLL_MS, tripKey, useAlerts } from '../AlertsProvider';

const A93 = alertFixture();
const A70 = alert70();

/** Minimal consumer: one status box per alert at 508 and a "Solicitar" for trip 12345. */
function Probe({ requestable }: { requestable: boolean }) {
  const { alertsAt, statusRef, requestButtonRef } = useAlerts();
  const alerts = alertsAt('508');
  return (
    <div>
      <p data-testid="alerts">{alerts.map((alert) => `${alert.line}:${alert.status}`).join(',')}</p>
      {alerts.map((alert) => (
        <div key={alert.alert_id} ref={statusRef(alert.alert_id)}>
          <button type="button">cancel {alert.line}</button>
        </div>
      ))}
      {requestable && !alerts.some((alert) => alert.trip_id === '12345') && (
        <button type="button" ref={requestButtonRef(tripKey(A93))}>
          request 93
        </button>
      )}
    </div>
  );
}

function Harness({ requestable = true }: { requestable?: boolean }) {
  const heading = useRef<HTMLHeadingElement>(null);
  return (
    <AlertsProvider fallbackFocus={heading}>
      <h2 ref={heading} tabIndex={-1}>
        heading
      </h2>
      <Probe requestable={requestable} />
    </AlertsProvider>
  );
}

function politeRegion(): HTMLElement {
  const region = document.querySelector<HTMLElement>('[aria-live="polite"]');
  if (region === null) throw new Error('no polite region');
  return region;
}

async function flush(ms = 0) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

function shownAlerts(): string {
  return screen.getByTestId('alerts').textContent ?? '';
}

describe('AlertsProvider', () => {
  let mineReply: () => FakeReply;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.spyOn(Math, 'random').mockReturnValue(0.5);
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(true);
    mineReply = () => ok({ alerts: [A93] });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  function api() {
    return mockApi((url) => {
      if (url.pathname === '/api/v1/alerts/mine') return mineReply();
      throw new Error(`unexpected request ${url.pathname}`);
    });
  }

  function connect(alerts = [A93]) {
    act(() => {
      FakeWebSocket.last().open();
      FakeWebSocket.last().receive({ type: 'alerts.snapshot', alerts });
    });
  }

  it('[passenger_alert_ui.AC-10] shows the snapshot of the WebSocket and applies the events', async () => {
    api();
    renderWithProviders(<Harness />);
    connect([A93, A70]);
    expect(shownAlerts()).toBe('93:PENDING_DRIVER,70:PENDING_DRIVER');

    act(() => FakeWebSocket.last().receive({ type: 'alert.cancelled', alert_id: A70.alert_id }));
    expect(shownAlerts()).toBe('93:PENDING_DRIVER');

    act(() =>
      FakeWebSocket.last().receive({
        type: 'alert.delivered',
        alert: { ...A93, status: 'DELIVERED' },
      }),
    );
    expect(shownAlerts()).toBe('93:DELIVERED');

    act(() => FakeWebSocket.last().receive({ type: 'alerts.snapshot', alerts: [A70] }));
    expect(shownAlerts()).toBe('70:PENDING_DRIVER');
  });

  it('[passenger_alert_ui.AC-10] while disconnected asks GET /alerts/mine every 30 s with X-Device-Id', async () => {
    const { fetchMock, calls } = api();
    renderWithProviders(<Harness />);

    await flush(FALLBACK_POLL_MS - 1);
    expect(calls('/alerts/mine')).toBe(0);
    await flush(1);
    expect(calls('/alerts/mine')).toBe(1);
    expect(shownAlerts()).toBe('93:PENDING_DRIVER');
    const [url, init] = fetchMock.mock.calls[0] ?? [];
    expect(String(url)).toBe('/api/v1/alerts/mine');
    expect(String(url)).not.toContain(getDeviceId());
    expect(new Headers(init?.headers).get('X-Device-Id')).toBe(getDeviceId());

    mineReply = () => ok({ alerts: [] });
    await flush(FALLBACK_POLL_MS);
    expect(calls('/alerts/mine')).toBe(2);
    expect(shownAlerts()).toBe('');
  });

  it('[passenger_alert_ui.AC-10] does not poll while connected, and polls again after the connection is lost', async () => {
    const { calls } = api();
    renderWithProviders(<Harness />);
    connect();

    await flush(5 * FALLBACK_POLL_MS);
    expect(calls('/alerts/mine')).toBe(0);

    act(() => FakeWebSocket.last().serverClose(1001));
    await flush(FALLBACK_POLL_MS);
    expect(calls('/alerts/mine')).toBe(1);
  });

  it('[passenger_alert_ui.AC-10] does not poll while the browser is offline', async () => {
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    const { calls } = api();
    renderWithProviders(<Harness />);

    await flush(3 * FALLBACK_POLL_MS);

    expect(calls('/alerts/mine')).toBe(0);
  });

  it('[passenger_alert_ui.AC-10] keeps the alerts when a poll fails', async () => {
    api();
    renderWithProviders(<Harness />);
    await flush(FALLBACK_POLL_MS);
    expect(shownAlerts()).toBe('93:PENDING_DRIVER');

    mineReply = () => {
      throw new Error('offline');
    };
    await flush(FALLBACK_POLL_MS);

    expect(shownAlerts()).toBe('93:PENDING_DRIVER');
  });

  it('[passenger_alert_ui.AC-11] announces delivered and expired politely, and nothing for the rest', async () => {
    api();
    renderWithProviders(<Harness />);
    connect([A93, A70]);
    await flush(100);
    expect(politeRegion()).toHaveTextContent('');

    act(() => FakeWebSocket.last().receive({ type: 'alert.registered', alert: A93 }));
    act(() => FakeWebSocket.last().receive({ type: 'alert.cancelled', alert_id: A70.alert_id }));
    await flush(100);
    expect(politeRegion()).toHaveTextContent('');

    act(() =>
      FakeWebSocket.last().receive({
        type: 'alert.delivered',
        alert: { ...A93, status: 'DELIVERED' },
      }),
    );
    await flush(100);
    expect(politeRegion()).toHaveTextContent(
      'El conductor de la línea 93 ha recibido tu solicitud',
    );

    act(() =>
      FakeWebSocket.last().receive({
        type: 'alert.expired',
        alert_id: A93.alert_id,
        reason: 'NEXT_STOP',
      }),
    );
    await flush(100);
    expect(politeRegion()).toHaveTextContent(
      'Tu solicitud de la línea 93 ha terminado: el autobús ya ha llegado a la parada siguiente',
    );
    expect(shownAlerts()).toBe('');
  });

  it('[passenger_alert_ui.AC-11] the focus on a control of an expired alert goes to "Solicitar" of its card', async () => {
    api();
    renderWithProviders(<Harness />);
    connect([A93]);
    screen.getByRole('button', { name: 'cancel 93' }).focus();

    act(() =>
      FakeWebSocket.last().receive({
        type: 'alert.expired',
        alert_id: A93.alert_id,
        reason: 'PASSED',
      }),
    );
    await flush();

    expect(screen.getByRole('button', { name: 'request 93' })).toHaveFocus();
  });

  it('[passenger_alert_ui.AC-11] without "Solicitar" the focus goes to the heading', async () => {
    api();
    renderWithProviders(<Harness requestable={false} />);
    connect([A93]);
    screen.getByRole('button', { name: 'cancel 93' }).focus();

    act(() => FakeWebSocket.last().receive({ type: 'alerts.snapshot', alerts: [] }));
    await flush();

    expect(screen.getByRole('heading', { name: 'heading' })).toHaveFocus();
  });

  it('[passenger_alert_ui.AC-11] the focus elsewhere is not moved when an alert goes away', async () => {
    api();
    renderWithProviders(<Harness />);
    connect([A93, A70]);
    const other = screen.getByRole('button', { name: 'cancel 70' });
    other.focus();

    act(() => FakeWebSocket.last().receive({ type: 'alert.cancelled', alert_id: A93.alert_id }));
    await flush();

    expect(other).toHaveFocus();
  });
});
