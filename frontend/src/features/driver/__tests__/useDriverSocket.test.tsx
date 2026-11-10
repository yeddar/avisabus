import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { FakeWebSocket } from '../../../test/FakeWebSocket';
import { mockApi, ok, problem } from '../../../test/mockApi';
import { getDriverToken, setDriverToken, subscribeDriverAuthLost } from '../session';
import { driverSocketUrl, useDriverSocket } from '../useDriverSocket';
import { driverView } from './fixtures';

const VIEW = { type: 'driver.view', ...driverView() };

function setOnline(value: boolean) {
  vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(value);
  act(() => {
    window.dispatchEvent(new Event(value ? 'online' : 'offline'));
  });
}

async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

function hook() {
  const onView = vi.fn();
  const onClosed = vi.fn();
  const rendered = renderHook(() => useDriverSocket({ onView, onClosed }));
  return { onView, onClosed, ...rendered };
}

function connectLast() {
  act(() => {
    FakeWebSocket.last().open();
    FakeWebSocket.last().receive(VIEW);
  });
}

describe('useDriverSocket', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    sessionStorage.clear();
    setDriverToken('token-1');
    FakeWebSocket.reset();
    vi.spyOn(Math, 'random').mockReturnValue(0.5);
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(true);
    mockApi(() => problem(500, 'unexpected'));
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('[driver_ui.AC-09] builds ws:// or wss:// from the origin without the token', () => {
    expect(driverSocketUrl({ protocol: 'http:', host: 'localhost:4173' })).toBe(
      'ws://localhost:4173/ws/driver',
    );
    expect(driverSocketUrl({ protocol: 'https:', host: 'avisabus.example' })).toBe(
      'wss://avisabus.example/ws/driver',
    );
  });

  it('[driver_ui.AC-09] opens /ws/driver and sends the hello with the token only in the message', () => {
    hook();

    const socket = FakeWebSocket.last();
    expect(socket.url).toBe(`ws://${window.location.host}/ws/driver`);
    expect(socket.url).not.toContain('token-1');

    act(() => socket.open());

    expect(socket.sentMessages()).toEqual([{ type: 'hello', session_token: 'token-1' }]);
  });

  it('[driver_ui.AC-09] is connected from the first view and answers ping with pong', () => {
    const { result } = hook();
    const socket = FakeWebSocket.last();

    act(() => socket.open());
    expect(result.current.status).toBe('connecting');

    act(() => socket.receive(VIEW));
    expect(result.current.status).toBe('connected');

    act(() => socket.receive({ type: 'ping' }));

    expect(socket.sentMessages()).toContainEqual({ type: 'pong' });
  });

  it('[driver_ui.AC-07] flags as initial the first view after entering and after reconnecting', async () => {
    const { onView } = hook();

    connectLast();
    act(() => FakeWebSocket.last().receive(VIEW));

    expect(onView.mock.calls.map(([, meta]) => (meta as { initial: boolean }).initial)).toEqual([
      true,
      false,
    ]);

    act(() => FakeWebSocket.last().serverClose(1006));
    await advance(1_000);
    connectLast();

    expect(onView.mock.calls.at(-1)?.[1]).toEqual({ initial: true });
  });

  it('[driver_ui.AC-09] reconnects with growing waits after a close and starts again after a view', async () => {
    const { result } = hook();
    connectLast();
    act(() => FakeWebSocket.last().serverClose(1012));

    expect(result.current.status).toBe('disconnected');
    expect(FakeWebSocket.instances).toHaveLength(1);

    await advance(999);
    expect(FakeWebSocket.instances).toHaveLength(1);
    await advance(1);
    expect(FakeWebSocket.instances).toHaveLength(2);

    act(() => FakeWebSocket.last().serverClose(1006));
    await advance(1_999);
    expect(FakeWebSocket.instances).toHaveLength(2);
    await advance(1);
    expect(FakeWebSocket.instances).toHaveLength(3);

    connectLast();
    act(() => FakeWebSocket.last().serverClose(1006));
    await advance(1_000);

    expect(FakeWebSocket.instances).toHaveLength(4);
  });

  it('[driver_ui.AC-09] does not reconnect while the browser is offline', async () => {
    const { result } = hook();
    connectLast();

    setOnline(false);

    expect(result.current.status).toBe('disconnected');
    expect(FakeWebSocket.last().closedByClient).toBe(1000);
    await advance(60_000);
    expect(FakeWebSocket.instances).toHaveLength(1);

    setOnline(true);

    expect(FakeWebSocket.instances).toHaveLength(2);
  });

  it('[driver_ui.AC-09] while disconnected asks for the view every 10 s and stops when connected', async () => {
    const api = mockApi(() => ok(driverView({ generated_at: '2026-11-09T07:42:00Z' })));
    const { onView } = hook();
    connectLast();
    act(() => FakeWebSocket.last().serverClose(1006));
    onView.mockClear();

    await advance(9_999);
    expect(api.calls('/current/view')).toBe(0);
    await advance(1);
    expect(api.calls('/current/view')).toBe(1);
    await advance(0);
    expect(onView).toHaveBeenCalledTimes(1);

    connectLast();
    await advance(30_000);

    expect(api.calls('/current/view')).toBe(1);
  });

  it('[driver_ui.AC-09] ignores a late view older than the last one', async () => {
    const newest = { type: 'driver.view', ...driverView({ generated_at: '2026-11-09T07:50:00Z' }) };
    const { onView } = hook();
    act(() => {
      FakeWebSocket.last().open();
      FakeWebSocket.last().receive(newest);
    });
    act(() => FakeWebSocket.last().serverClose(1006));
    mockApi(() => ok(driverView({ generated_at: '2026-11-09T07:49:00Z' })));
    onView.mockClear();

    await advance(10_000);

    expect(onView).not.toHaveBeenCalled();
  });

  it('[driver_ui.AC-10] passes session.closed on, and does not reconnect after it', async () => {
    const { onClosed } = hook();
    connectLast();

    act(() => FakeWebSocket.last().receive({ type: 'session.closed', reason: 'IDLE' }));
    expect(onClosed).toHaveBeenCalledWith('IDLE');

    act(() => FakeWebSocket.last().serverClose(1000));
    await advance(60_000);

    expect(FakeWebSocket.instances).toHaveLength(1);
  });

  it('[driver_ui.AC-03] the close 4401 ends the session without reconnecting', async () => {
    const lost = vi.fn();
    const unsubscribe = subscribeDriverAuthLost(lost);
    hook();

    act(() => FakeWebSocket.last().serverClose(4401));
    await advance(60_000);

    expect(lost).toHaveBeenCalledTimes(1);
    expect(getDriverToken()).toBeNull();
    expect(FakeWebSocket.instances).toHaveLength(1);
    unsubscribe();
  });

  it('[driver_ui.AC-09] closes the socket when unmounted and ignores malformed frames', () => {
    const { onView, unmount } = hook();
    const socket = FakeWebSocket.last();
    act(() => socket.open());

    act(() => socket.receive('not json'));
    act(() => socket.receive({ type: 'driver.view' }));
    expect(onView).not.toHaveBeenCalled();

    unmount();

    expect(socket.closedByClient).toBe(1000);
  });
});
