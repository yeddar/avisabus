import { useEffect, useRef, useState } from 'react';

import { driverApi } from './session';

const SEND_INTERVAL_MS = 5_000;
/** Silence of watchPosition after which a fresh fix is requested explicitly (AC-04 v1.1). */
const SILENCE_MS = 10_000;
const CURRENT_POSITION_OPTIONS: PositionOptions = {
  enableHighAccuracy: true,
  maximumAge: 0,
  timeout: SILENCE_MS,
};
const PERMISSION_DENIED = 1;

export type LocationPermission = 'prompt' | 'granted' | 'denied';

function supported(): boolean {
  return typeof navigator !== 'undefined' && 'geolocation' in navigator && !!navigator.geolocation;
}

/**
 * Follows the device position while `enabled` (driver_ui.AC-04 v1.1): watchPosition with high
 * accuracy, and every 5 s the latest fix through PUT position, even if it repeats: the resend is
 * the sign of life of the shift, and only a fix with a newer `recorded_at` counts as GPS for the
 * server (driver_session.AC-08, AC-11). If watchPosition delivers nothing for 10 s (a bus standing
 * still may get no updates), it asks for a fresh fix with getCurrentPosition, again every 10 s
 * while the silence lasts, so only a lost GPS ends in "Posición desactualizada". Also keeps the
 * screen awake with the Wake Lock API, requesting it again when the page becomes visible; without
 * that API or its permission nothing fails.
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
    let silence: ReturnType<typeof setTimeout> | undefined;

    function onPosition(position: GeolocationPosition) {
      latest.current = position;
      setPermission('granted');
    }

    function onError(error: GeolocationPositionError) {
      if (error.code !== PERMISSION_DENIED) return;
      setPermission('denied');
      // Nothing to ask for until "Reintentar" restarts the watch.
      clearTimeout(silence);
    }

    function watchSilence() {
      clearTimeout(silence);
      silence = setTimeout(() => {
        geolocation.getCurrentPosition(onPosition, onError, CURRENT_POSITION_OPTIONS);
        watchSilence();
      }, SILENCE_MS);
    }

    const watchId = geolocation.watchPosition(
      (position) => {
        onPosition(position);
        watchSilence();
      },
      onError,
      { enableHighAccuracy: true },
    );
    watchSilence();
    const timer = setInterval(() => {
      const position = latest.current;
      if (position === null) return;
      // A failed send is dropped: the next tick sends again. A 401 ends the session.
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
      clearTimeout(silence);
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
