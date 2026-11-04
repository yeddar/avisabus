import type { FitBoundsOptions } from 'leaflet';
import { useEffect, useRef } from 'react';

import type { Bounds } from './mapModel';

/** Margin around the framed points and the closest zoom (bus and stop can coincide). */
export const FIT_OPTIONS: FitBoundsOptions = { padding: [40, 40], maxZoom: 17, animate: false };

/**
 * Frames `bounds` the first time the data are `ready` and never again, so later refreshes do not
 * move the map while the person uses it (passenger_map_view.AC-08).
 */
export function useInitialFit(
  map: { fitBounds: (bounds: Bounds, options?: FitBoundsOptions) => unknown },
  bounds: Bounds,
  ready: boolean,
): void {
  const done = useRef(false);

  useEffect(() => {
    if (done.current || !ready) return;
    done.current = true;
    map.fitBounds(bounds, FIT_OPTIONS);
  }, [map, bounds, ready]);
}
