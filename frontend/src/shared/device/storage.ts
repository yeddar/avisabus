/**
 * Device-local state (conventions §4). The only keys:
 * - `avisabus.deviceId`: anonymous device identifier (passenger_alert_ui.AC-01, deviceId.ts);
 * - `avisabus.language`: interface language (frontend_i18n);
 * - `avisabus.needsProfile`: accessibility profile (passenger_alert_ui.AC-02, needsProfile.ts);
 * - `avisabus.lastStop`: last stop viewed, with stop_id, name and the public QR token
 *   (passenger_stop_view.AC-19).
 * Access to localStorage can throw (private mode, disabled storage, quota), so every call is
 * guarded and failures degrade to "nothing stored".
 */
export const safeStorage = {
  get(key: string): string | null {
    try {
      return window.localStorage.getItem(key);
    } catch {
      return null;
    }
  },
  set(key: string, value: string): void {
    try {
      window.localStorage.setItem(key, value);
    } catch {
      // Storage unavailable: the choice simply is not remembered.
    }
  },
  remove(key: string): void {
    try {
      window.localStorage.removeItem(key);
    } catch {
      // Storage unavailable: there is nothing stored to remove.
    }
  },
};
