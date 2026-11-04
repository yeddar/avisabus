import { renderHook } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import type { Bounds } from '../mapModel';
import { FIT_OPTIONS, useInitialFit } from '../useInitialFit';

const FIRST: Bounds = [
  [39.46, -0.41],
  [39.47, -0.39],
];
const LATER: Bounds = [
  [39.465, -0.4],
  [39.468, -0.395],
];

function fakeMap() {
  return { fitBounds: vi.fn() };
}

describe('useInitialFit', () => {
  it('[passenger_map_view.AC-08] frames the first bounds once the data are ready', () => {
    const map = fakeMap();
    const { rerender } = renderHook(({ bounds, ready }) => useInitialFit(map, bounds, ready), {
      initialProps: { bounds: FIRST, ready: false },
    });
    expect(map.fitBounds).not.toHaveBeenCalled();

    rerender({ bounds: FIRST, ready: true });

    expect(map.fitBounds).toHaveBeenCalledExactlyOnceWith(FIRST, FIT_OPTIONS);
  });

  it('[passenger_map_view.AC-08] does not frame again on later refreshes', () => {
    const map = fakeMap();
    const { rerender } = renderHook(({ bounds }) => useInitialFit(map, bounds, true), {
      initialProps: { bounds: FIRST },
    });

    rerender({ bounds: LATER });
    rerender({ bounds: FIRST });

    expect(map.fitBounds).toHaveBeenCalledTimes(1);
    expect(map.fitBounds).toHaveBeenCalledWith(FIRST, FIT_OPTIONS);
  });

  it('[passenger_map_view.AC-08] frames without animation and never closer than street level', () => {
    expect(FIT_OPTIONS).toMatchObject({ animate: false, maxZoom: 17 });
  });
});
