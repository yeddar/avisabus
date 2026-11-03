import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { SERVER_CLOCK_TICK_MS, useServerNow } from '../useServerNow';

const DEVICE_NOW = Date.parse('2026-11-04T07:40:00Z');

describe('useServerNow', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(DEVICE_NOW);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('[passenger_stop_view.AC-13] corrects the device clock with the server generated_at', () => {
    // The server is 90 s ahead of the device.
    const { result } = renderHook(() => useServerNow('2026-11-04T07:41:30Z'));

    expect(result.current.toISOString()).toBe('2026-11-04T07:41:30.000Z');
  });

  it('[passenger_stop_view.AC-13] moves forward every 15 s keeping the offset', () => {
    const { result } = renderHook(() => useServerNow('2026-11-04T07:38:00Z'));
    expect(SERVER_CLOCK_TICK_MS).toBe(15_000);

    act(() => {
      vi.advanceTimersByTime(14_999);
    });
    expect(result.current.toISOString()).toBe('2026-11-04T07:38:00.000Z');

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(result.current.toISOString()).toBe('2026-11-04T07:38:15.000Z');

    act(() => {
      vi.advanceTimersByTime(45_000);
    });
    expect(result.current.toISOString()).toBe('2026-11-04T07:39:00.000Z');
  });

  it('[passenger_stop_view.AC-13] recomputes the offset when a new response arrives', () => {
    const { result, rerender } = renderHook(({ at }) => useServerNow(at), {
      initialProps: { at: '2026-11-04T07:40:00Z' },
    });
    act(() => {
      vi.advanceTimersByTime(30_000);
    });
    expect(result.current.toISOString()).toBe('2026-11-04T07:40:30.000Z');

    // New response: the server says it is 07:41:00 when the device says 07:40:30.
    rerender({ at: '2026-11-04T07:41:00Z' });

    expect(result.current.toISOString()).toBe('2026-11-04T07:41:00.000Z');
  });

  it('[passenger_stop_view.AC-13] uses the device clock until there is a response', () => {
    const { result } = renderHook(() => useServerNow(undefined));

    expect(result.current.getTime()).toBe(DEVICE_NOW);
  });

  it('[passenger_stop_view.AC-13] accepts a custom tick', () => {
    const { result } = renderHook(() => useServerNow('2026-11-04T07:40:00Z', 1_000));

    act(() => {
      vi.advanceTimersByTime(1_000);
    });

    expect(result.current.toISOString()).toBe('2026-11-04T07:40:01.000Z');
  });
});
