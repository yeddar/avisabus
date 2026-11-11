import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { mockApi, ok, problem } from '../../../test/mockApi';
import { setDriverToken } from '../session';
import { useDriverPosition } from '../useDriverPosition';

type Fix = { coords: { latitude: number; longitude: number; accuracy: number }; timestamp: number };

function fix(latitude: number, timestamp: number): Fix {
  return { coords: { latitude, longitude: -0.37, accuracy: 12 }, timestamp };
}

class FakeGeolocation {
  success: ((position: Fix) => void) | null = null;
  failure: ((error: { code: number; PERMISSION_DENIED: number }) => void) | null = null;
  options: PositionOptions | undefined;
  watches = 0;
  cleared = 0;

  watchPosition = vi.fn(
    (
      success: (position: Fix) => void,
      failure: (error: { code: number; PERMISSION_DENIED: number }) => void,
      options?: PositionOptions,
    ) => {
      this.success = success;
      this.failure = failure;
      this.options = options;
      this.watches += 1;
      return this.watches;
    },
  );

  clearWatch = vi.fn(() => {
    this.cleared += 1;
  });

  current: ((position: Fix) => void) | null = null;
  currentOptions: PositionOptions | undefined;

  getCurrentPosition = vi.fn(
    (
      success: (position: Fix) => void,
      _failure: (error: { code: number; PERMISSION_DENIED: number }) => void,
      options?: PositionOptions,
    ) => {
      this.current = success;
      this.currentOptions = options;
    },
  );

  /** Answers the pending getCurrentPosition() request. */
  answerCurrent(position: Fix) {
    act(() => this.current?.(position));
  }

  emit(position: Fix) {
    act(() => this.success?.(position));
  }

  deny() {
    act(() => this.failure?.({ code: 1, PERMISSION_DENIED: 1 }));
  }
}

function stubGeolocation(fake: FakeGeolocation | undefined) {
  Object.defineProperty(navigator, 'geolocation', { configurable: true, value: fake });
}

function stubWakeLock(request: ReturnType<typeof vi.fn> | undefined) {
  Object.defineProperty(navigator, 'wakeLock', {
    configurable: true,
    value: request === undefined ? undefined : { request },
  });
}

function setVisibility(state: 'visible' | 'hidden') {
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => state });
  act(() => {
    document.dispatchEvent(new Event('visibilitychange'));
  });
}

async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

function positionCalls(api: ReturnType<typeof mockApi>) {
  return api.fetchMock.mock.calls
    .filter(([input]) => String(input).includes('/current/position'))
    .map(([, init]) => JSON.parse(String(init?.body)) as Record<string, unknown>);
}

describe('useDriverPosition', () => {
  let geolocation: FakeGeolocation;

  beforeEach(() => {
    vi.useFakeTimers();
    sessionStorage.clear();
    setDriverToken('token-1');
    geolocation = new FakeGeolocation();
    stubGeolocation(geolocation);
    stubWakeLock(undefined);
    setVisibility('visible');
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    stubGeolocation(undefined);
    stubWakeLock(undefined);
  });

  it('[driver_ui.AC-04] follows the position with high accuracy and only while enabled', () => {
    mockApi(() => ok(null));
    const { rerender, unmount } = renderHook(({ on }) => useDriverPosition(on), {
      initialProps: { on: false },
    });

    expect(geolocation.watchPosition).not.toHaveBeenCalled();

    rerender({ on: true });

    expect(geolocation.watchPosition).toHaveBeenCalledTimes(1);
    expect(geolocation.options?.enableHighAccuracy).toBe(true);

    unmount();

    expect(geolocation.clearWatch).toHaveBeenCalledTimes(1);
  });

  it('[driver_ui.AC-04] sends the latest fix every 5 s through PUT position', async () => {
    const api = mockApi(() => ({ status: 204, body: null }));
    renderHook(() => useDriverPosition(true));

    geolocation.emit(fix(39.46, Date.UTC(2026, 10, 9, 7, 41, 0)));
    geolocation.emit(fix(39.47, Date.UTC(2026, 10, 9, 7, 41, 3)));

    await advance(4_999);
    expect(positionCalls(api)).toHaveLength(0);

    await advance(1);

    expect(positionCalls(api)).toEqual([
      {
        lat: 39.47,
        lon: -0.37,
        accuracy_m: 12,
        recorded_at: '2026-11-09T07:41:03.000Z',
      },
    ]);
  });

  it('[driver_ui.AC-04] sends the latest fix again every 5 s even if it repeats: it is the sign of life', async () => {
    const api = mockApi(() => ({ status: 204, body: null }));
    renderHook(() => useDriverPosition(true));
    geolocation.emit(fix(39.46, Date.UTC(2026, 10, 9, 7, 41, 0)));

    await advance(15_000);

    const repeated = {
      lat: 39.46,
      lon: -0.37,
      accuracy_m: 12,
      recorded_at: '2026-11-09T07:41:00.000Z',
    };
    expect(positionCalls(api)).toEqual([repeated, repeated, repeated]);

    geolocation.emit(fix(39.47, Date.UTC(2026, 10, 9, 7, 41, 20)));
    await advance(5_000);

    expect(positionCalls(api).at(-1)).toMatchObject({
      lat: 39.47,
      recorded_at: '2026-11-09T07:41:20.000Z',
    });
  });

  it('[driver_ui.AC-04] sends nothing until there is a first fix', async () => {
    const api = mockApi(() => ({ status: 204, body: null }));
    renderHook(() => useDriverPosition(true));

    await advance(9_000);

    expect(positionCalls(api)).toHaveLength(0);
  });

  it('[driver_ui.AC-04] asks getCurrentPosition when watchPosition delivers nothing in 10 s', async () => {
    const api = mockApi(() => ({ status: 204, body: null }));
    renderHook(() => useDriverPosition(true));
    geolocation.emit(fix(39.46, Date.UTC(2026, 10, 9, 7, 41, 0)));

    await advance(9_999);
    expect(geolocation.getCurrentPosition).not.toHaveBeenCalled();

    await advance(1);

    expect(geolocation.getCurrentPosition).toHaveBeenCalledTimes(1);
    expect(geolocation.currentOptions).toEqual({
      enableHighAccuracy: true,
      maximumAge: 0,
      timeout: 10_000,
    });

    geolocation.answerCurrent(fix(39.48, Date.UTC(2026, 10, 9, 7, 41, 12)));
    await advance(5_000);

    expect(positionCalls(api).at(-1)).toMatchObject({
      lat: 39.48,
      recorded_at: '2026-11-09T07:41:12.000Z',
    });

    // Still silent: it keeps asking every 10 s.
    await advance(5_000);
    expect(geolocation.getCurrentPosition).toHaveBeenCalledTimes(2);
  });

  it('[driver_ui.AC-04] does not ask getCurrentPosition while watchPosition keeps delivering', async () => {
    mockApi(() => ({ status: 204, body: null }));
    renderHook(() => useDriverPosition(true));

    for (let second = 0; second < 30; second += 6) {
      geolocation.emit(fix(39.46, Date.UTC(2026, 10, 9, 7, 41, second)));
      await advance(6_000);
    }

    expect(geolocation.getCurrentPosition).not.toHaveBeenCalled();
  });

  it('[driver_ui.AC-04] also asks getCurrentPosition when watchPosition never delivers', async () => {
    mockApi(() => ({ status: 204, body: null }));
    const { unmount } = renderHook(() => useDriverPosition(true));

    await advance(10_000);

    expect(geolocation.getCurrentPosition).toHaveBeenCalledTimes(1);

    unmount();
    await advance(30_000);

    expect(geolocation.getCurrentPosition).toHaveBeenCalledTimes(1);
  });

  it('[driver_ui.AC-04] reports a denied permission and "Reintentar" watches again', () => {
    mockApi(() => ok(null));
    const { result } = renderHook(() => useDriverPosition(true));

    expect(result.current.permission).toBe('prompt');

    geolocation.deny();

    expect(result.current.permission).toBe('denied');

    act(() => result.current.retry());

    expect(geolocation.watchPosition).toHaveBeenCalledTimes(2);
    expect(result.current.permission).toBe('prompt');

    geolocation.emit(fix(39.46, 1));

    expect(result.current.permission).toBe('granted');
  });

  it('[driver_ui.AC-04] with the permission denied it stops asking getCurrentPosition', async () => {
    mockApi(() => ok(null));
    renderHook(() => useDriverPosition(true));

    geolocation.deny();
    await advance(30_000);

    expect(geolocation.getCurrentPosition).not.toHaveBeenCalled();
  });

  it('[driver_ui.AC-04] without geolocation it reports denied and does not fail', () => {
    stubGeolocation(undefined);
    mockApi(() => ok(null));

    const { result } = renderHook(() => useDriverPosition(true));

    expect(result.current.permission).toBe('denied');
  });

  it('[driver_ui.AC-03] a 401 while sending goes through the session-lost path without throwing', async () => {
    mockApi(() => problem(401, 'invalid-session'));
    renderHook(() => useDriverPosition(true));
    geolocation.emit(fix(39.46, 1));

    await advance(5_000);

    expect(sessionStorage.getItem('avisabus.driverSession')).toBeNull();
  });

  it('[driver_ui.AC-04] requests the screen wake lock and requests it again when the page becomes visible', async () => {
    mockApi(() => ok(null));
    const release = vi.fn(() => Promise.resolve());
    const request = vi.fn(() => Promise.resolve({ release }));
    stubWakeLock(request);

    const { unmount } = renderHook(() => useDriverPosition(true));
    await advance(0);

    expect(request).toHaveBeenCalledWith('screen');

    setVisibility('hidden');
    await advance(0);
    expect(request).toHaveBeenCalledTimes(1);

    setVisibility('visible');
    await advance(0);
    expect(request).toHaveBeenCalledTimes(2);

    unmount();

    expect(release).toHaveBeenCalled();
  });

  it('[driver_ui.AC-04] does not fail without wakeLock or when the request is rejected', async () => {
    mockApi(() => ok(null));
    stubWakeLock(undefined);
    const first = renderHook(() => useDriverPosition(true));
    await advance(0);
    first.unmount();

    stubWakeLock(vi.fn(() => Promise.reject(new Error('NotAllowedError'))));
    renderHook(() => useDriverPosition(true));

    await expect(advance(0)).resolves.toBeUndefined();
  });
});
