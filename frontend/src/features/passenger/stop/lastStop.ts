import { safeStorage } from '../../../shared/device/storage';

/** Last stop opened on this device, offered on the home page (passenger_stop_view.AC-19). */
export type LastStop = { stopId: string; name: string; token: string };

export const LAST_STOP_STORAGE_KEY = 'avisabus.lastStop';

function isLastStop(value: unknown): value is LastStop {
  if (typeof value !== 'object' || value === null) return false;
  const record = value as Record<string, unknown>;
  return (
    typeof record.stopId === 'string' &&
    typeof record.name === 'string' &&
    typeof record.token === 'string'
  );
}

export function getLastStop(): LastStop | null {
  const raw = safeStorage.get(LAST_STOP_STORAGE_KEY);
  if (raw === null) return null;
  try {
    const value: unknown = JSON.parse(raw);
    return isLastStop(value)
      ? { stopId: value.stopId, name: value.name, token: value.token }
      : null;
  } catch {
    return null;
  }
}

export function setLastStop(stop: LastStop): void {
  safeStorage.set(
    LAST_STOP_STORAGE_KEY,
    JSON.stringify({ stopId: stop.stopId, name: stop.name, token: stop.token }),
  );
}
