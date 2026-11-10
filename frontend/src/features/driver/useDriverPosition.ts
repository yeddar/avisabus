import { useEffect, useRef, useState } from 'react';

import { driverApi } from './session';

const SEND_INTERVAL_MS = 5_000;
const PERMISSION_DENIED = 1;

export type LocationPermission = 'prompt' | 'granted' | 'denied';

function supported(): boolean {
  return typeof navigator !== 'undefined' && 'geolocation' in navigator && !!navigator.geolocation;
}

/**
 * Follows the device position while `enabled` (driver_ui.AC-04): watchPosition with high accuracy,
 * the latest fix sent every 5 s with PUT position. A fix is sent once: the server decides that
 * the GPS is lost from the arrival of positions (driver_session.AC-11, CU-09 1a), so repeating
 * an old one would hide it. Also keeps the screen awake with the Wake Lock API, requesting it
 * again when the page becomes visible; without that API or its permission nothing fails.
 */
export function useDriverPosition(enabled: boolean): {
  permission: LocationPermission;
  retry(): void;
} {
  const [permission, setPermission] = useState<LocationPermission>(() =>
    supported() ? 'prompt' : 'denied',
  );
  const [attempt, setAttempt] = useState(0);
  const latest = useRef<GeolocationPosition | null>(null);

  useEffect(() => {
    if (!enabled || !supported()) return;
    const { geolocation } = navigator;
    const watchId = geolocation.watchPosition(
      (position) => {
        latest.current = position;
        setPermission('granted');
      },
      (error) => {
        if (error.code === PERMISSION_DENIED) setPermission('denied');
      },
      { enableHighAccuracy: true },
    );
    const timer = setInterval(() => {
      const position = latest.current;
      if (position === null) return;
      latest.current = null;
      // A failed send is dropped: the next tick has a newer fix. A 401 ends the session.
      void driverApi('PUT', '/driver/sessions/current/position', {
        lat: position.coords.latitude,
        lon: position.coords.longitude,
        accuracy_m: position.coords.accuracy,
        recorded_at: new Date(position.timestamp).toISOString(),
      }).catch(() => undefined);
    }, SEND_INTERVAL_MS);
    return () => {
      geolocation.clearWatch(watchId);
      clearInterval(timer);
    };
  }, [enabled, attempt]);

  useEffect(() => {
    if (!enabled) return;
    let lock: WakeLockSentinel | null = null;
    let released = false;

    async function request() {
      if (navigator.wakeLock === undefined) return;
      try {
        const sentinel = await navigator.wakeLock.request('screen');
        if (released) void sentinel.release();
        else lock = sentinel;
      } catch {
        // Not available right now (e.g. low battery): the view works without it.
      }
    }

    function onVisibility() {
      if (document.visibilityState === 'visible') void request();
    }

    void request();
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      released = true;
      document.removeEventListener('visibilitychange', onVisibility);
      if (lock !== null) void lock.release();
    };
  }, [enabled]);

  return {
    permission,
    retry() {
      setPermission(supported() ? 'prompt' : 'denied');
      setAttempt((value) => value + 1);
    },
  };
}
