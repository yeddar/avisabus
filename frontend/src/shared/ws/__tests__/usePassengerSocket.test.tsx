import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { alertFixture } from '../../../test/fixtures/alerts';
import { FakeWebSocket } from '../../../test/FakeWebSocket';
import { getDeviceId } from '../../device/deviceId';
import { passengerSocketUrl, usePassengerSocket } from '../usePassengerSocket';

const SNAPSHOT = { type: 'alerts.snapshot', alerts: [alertFixture()] };

function setOnline(value: boolean) {
  vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(value);
  act(() => {
    window.dispatchEvent(new Event(value ? 'online' : 'offline'));
  });
}

/** Opens the last socket and answers the hello with an empty snapshot. */
function connectLast() {
  act(() => {
    FakeWebSocket.last().open();
    FakeWebSocket.last().receive({ type: 'alerts.snapshot', alerts: [] });
  });
}

async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe('usePassengerSocket', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    // Centre of the ±20 % variation: the waits are exactly 1, 2, 4… s.
    vi.spyOn(Math, 'random').mockReturnValue(0.5);
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(true);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('[passenger_alert_ui.AC-10] builds ws:// or wss:// from the page origin, without the device id', () => {
    expect(passengerSocketUrl({ protocol: 'http:', host: 'localhost:4173' })).toBe(
      'ws://localhost:4173/ws/passenger',
    );
    expect(passengerSocketUrl({ protocol: 'https:', host: 'avisabus.example' })).toBe(
      'wss://avisabus.example/ws/passenger',
    );
  });

  it('[passenger_alert_ui.AC-10] [passenger_alert_ui.AC-01] opens /ws/passenger and sends the hello with the device id only in the message', () => {
    renderHook(() => usePassengerSocket(vi.fn()));

    expect(FakeWebSocket.instances).toHaveLength(1);
    const socket = FakeWebSocket.last();
    expect(socket.url).toBe(`ws://${window.location.host}/ws/passenger`);
    expect(socket.url).not.toContain(getDeviceId());

    act(() => socket.open());

    expect(socket.sentMessages()).toEqual([{ type: 'hello', device_id: getDeviceId() }]);
  });

  it('[passenger_alert_ui.AC-10] is connected after the snapshot and passes it and every event on', () => {
    const onMessage = vi.fn();
    const { result } = renderHook(() => usePassengerSocket(onMessage));
    const socket = FakeWebSocket.last();

    act(() => socket.open());
    expect(result.current.connected).toBe(false);

    act(() => socket.receive(SNAPSHOT));
    expect(result.current.connected).toBe(true);

    const delivered = { type: 'alert.delivered', alert: alertFixture({ status: 'DELIVERED' }) };
    const expired = { type: 'alert.expired', alert_id: 'x', reason: 'PASSED' };
    act(() => {
      socket.receive(delivered);
      socket.receive(expired);
    });

    expect(onMessage.mock.calls.map(([message]) => message)).toEqual([
      SNAPSHOT,
      delivered,
      expired,
    ]);
  });

  it('[passenger_alert_ui.AC-10] answers each ping with a pong and does not pass it on', () => {
    const onMessage = vi.fn();
    renderHook(() => usePassengerSocket(onMessage));
    const socket = FakeWebSocket.last();
    act(() => socket.open());

    act(() => socket.receive({ type: 'ping' }));

    expect(socket.sentMessages().at(-1)).toEqual({ type: 'pong' });
    expect(onMessage).not.toHaveBeenCalled();
  });

  it('[passenger_alert_ui.AC-10] ignores frames that are not valid messages', () => {
    const onMessage = vi.fn();
    renderHook(() => usePassengerSocket(onMessage));
    const socket = FakeWebSocket.last();
    act(() => socket.open());

    act(() => {
      socket.receive('{not json');
      socket.receive({ type: 'alert.unknown' });
      socket.receive({ type: 'alert.expired', alert_id: 'x', reason: 'LATER' });
      socket.receive({ type: 'alerts.snapshot', alerts: 'none' });
      socket.receive({ type: 'alert.registered', alert: { alert_id: 3 } });
    });

    expect(onMessage).not.toHaveBeenCalled();
  });

  it.each([1000, 1001, 1006, 1011, 1012, 1013, 4400, 4408, 4429])(
    '[passenger_alert_ui.AC-10] reconnects after 1 s when the connection closes with code %i',
    async (code) => {
      const { result } = renderHook(() => usePassengerSocket(vi.fn()));
      connectLast();
      expect(result.current.connected).toBe(true);

      act(() => FakeWebSocket.last().serverClose(code));
      expect(result.current.connected).toBe(false);

      await advance(999);
      expect(FakeWebSocket.instances).toHaveLength(1);
      await advance(1);
      expect(FakeWebSocket.instances).toHaveLength(2);
    },
  );

  it('[passenger_alert_ui.AC-10] waits 1, 2, 4, 8, 16, 30 and 30 s between failed attempts', async () => {
    renderHook(() => usePassengerSocket(vi.fn()));
    const waits: number[] = [];

    for (const expected of [1, 2, 4, 8, 16, 30, 30]) {
      const before = FakeWebSocket.instances.length;
      act(() => FakeWebSocket.last().serverClose(1006));
      await advance(expected * 1000 - 1);
      expect(FakeWebSocket.instances).toHaveLength(before);
      await advance(1);
      expect(FakeWebSocket.instances).toHaveLength(before + 1);
      waits.push(expected);
    }

    expect(waits).toEqual([1, 2, 4, 8, 16, 30, 30]);
  });

  it('[passenger_alert_ui.AC-10] a snapshot resets the waits to 1 s', async () => {
    renderHook(() => usePassengerSocket(vi.fn()));
    for (const wait of [1, 2, 4]) {
      act(() => FakeWebSocket.last().serverClose(1006));
      await advance(wait * 1000);
    }
    connectLast();

    act(() => FakeWebSocket.last().serverClose(1012));
    const before = FakeWebSocket.instances.length;
    await advance(1000);

    expect(FakeWebSocket.instances).toHaveLength(before + 1);
  });

  it('[passenger_alert_ui.AC-10] applies the random variation to the waits', async () => {
    vi.spyOn(Math, 'random').mockReturnValue(0);
    renderHook(() => usePassengerSocket(vi.fn()));

    act(() => FakeWebSocket.last().serverClose(1006));
    await advance(799);
    expect(FakeWebSocket.instances).toHaveLength(1);
    await advance(1);
    expect(FakeWebSocket.instances).toHaveLength(2);
  });

  it('[passenger_alert_ui.AC-10] does not reconnect while there is no network, and reconnects when it comes back', async () => {
    const { result } = renderHook(() => usePassengerSocket(vi.fn()));
    connectLast();

    setOnline(false);
    act(() => FakeWebSocket.last().serverClose(1006));
    expect(result.current.connected).toBe(false);
    await advance(120_000);
    expect(FakeWebSocket.instances).toHaveLength(1);

    setOnline(true);
    expect(FakeWebSocket.instances).toHaveLength(2);
    connectLast();
    expect(result.current.connected).toBe(true);
  });

  it('[passenger_alert_ui.AC-10] does not open a socket while offline', async () => {
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    renderHook(() => usePassengerSocket(vi.fn()));

    await advance(60_000);

    expect(FakeWebSocket.instances).toHaveLength(0);
  });

  it('[passenger_alert_ui.AC-10] closes the socket when the view goes away and does not reconnect', async () => {
    const { unmount } = renderHook(() => usePassengerSocket(vi.fn()));
    connectLast();
    const socket = FakeWebSocket.last();

    unmount();
    await advance(60_000);

    expect(socket.closedByClient).toBe(1000);
    expect(FakeWebSocket.instances).toHaveLength(1);
  });
});
