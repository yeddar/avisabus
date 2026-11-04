import { safeStorage } from './storage';

/**
 * Anonymous identifier of the device (passenger_alert_ui.AC-01): a random UUID v4 kept on the
 * device. It only ever travels in the X-Device-Id header and in the WebSocket `hello`, never
 * in a URL, and is never logged.
 */
export const DEVICE_ID_STORAGE_KEY = 'avisabus.deviceId';

/** Canonical UUID v4, the only form the API accepts (realtime_events.AC-04). */
const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

/** Identifier of this session; the only copy when the storage is not available. */
let current: string | null = null;

export function getDeviceId(): string {
  if (current !== null) return current;
  const stored = safeStorage.get(DEVICE_ID_STORAGE_KEY);
  if (stored !== null && UUID_V4.test(stored)) {
    current = stored;
  } else {
    current = crypto.randomUUID();
    safeStorage.set(DEVICE_ID_STORAGE_KEY, current);
  }
  return current;
}
