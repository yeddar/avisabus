/**
 * Device-local state (conventions §4): only device_id, language and accessibility profile live
 * here. Access to localStorage can throw (private mode, disabled storage, quota), so every call
 * is guarded and failures degrade to "nothing stored".
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
};
