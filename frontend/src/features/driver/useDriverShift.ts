import { useCallback, useRef } from 'react';

import type { DriverView } from './types';
import { type LocationPermission, useDriverPosition } from './useDriverPosition';
import {
  type DriverSocketStatus,
  type SessionCloseReason,
  useDriverSocket,
} from './useDriverSocket';

/** A view from the socket or the polling; `initial`: first one after entering or reconnecting. */
export type DriverViewListener = (view: DriverView, meta: { initial: boolean }) => void;

export interface DriverShift {
  permission: LocationPermission;
  retryPermission(): void;
  socketStatus: DriverSocketStatus;
  /** Listens to every view of the shift; returns the function that stops listening. */
  subscribeViews(listener: DriverViewListener): () => void;
}

/**
 * What lasts as long as the open shift on /driver/shift, whatever the step (driver_ui.AC-04,
 * AC-08, AC-09 v1.1): the position, the wake lock and /ws/driver with its polling. It lives in
 * ShiftPage, so choosing the next departure does not interrupt any of them.
 */
export function useDriverShift(
  enabled: boolean,
  onClosed: (reason: SessionCloseReason) => void,
): DriverShift {
  const { permission, retry } = useDriverPosition(enabled);
  const listeners = useRef(new Set<DriverViewListener>());

  const { status } = useDriverSocket({
    enabled,
    onView(view, meta) {
      listeners.current.forEach((listener) => listener(view, meta));
    },
    onClosed,
  });

  const subscribeViews = useCallback((listener: DriverViewListener) => {
    const current = listeners.current;
    current.add(listener);
    return () => {
      current.delete(listener);
    };
  }, []);

  return { permission, retryPermission: retry, socketStatus: status, subscribeViews };
}
