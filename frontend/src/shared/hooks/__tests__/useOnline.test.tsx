import { act, renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { useOnline } from '../useOnline';

function setNavigatorOnline(value: boolean) {
  vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(value);
}

describe('useOnline', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('[passenger_stop_view.AC-18] starts with the browser connection state', () => {
    setNavigatorOnline(false);

    const { result } = renderHook(() => useOnline());

    expect(result.current).toBe(false);
  });

  it('[passenger_stop_view.AC-18] follows the offline and online events', () => {
    setNavigatorOnline(true);
    const { result } = renderHook(() => useOnline());
    expect(result.current).toBe(true);

    act(() => {
      setNavigatorOnline(false);
      window.dispatchEvent(new Event('offline'));
    });
    expect(result.current).toBe(false);

    act(() => {
      setNavigatorOnline(true);
      window.dispatchEvent(new Event('online'));
    });
    expect(result.current).toBe(true);
  });
});
