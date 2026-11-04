import type { Need } from '../api/types';
import { safeStorage } from './storage';

export type { Need };

/** Accessibility profile of the passenger (RF-18): only on the device, never sent on its own. */
export const NEEDS_PROFILE_STORAGE_KEY = 'avisabus.needsProfile';

/** The four needs in the canonical order of the API (alert_create.AC-06). */
export const NEEDS: readonly Need[] = ['RAMP', 'EXTRA_TIME', 'SEAT', 'VISUAL'];

/** Known needs of `values`, once each, in canonical order. */
export function canonicalNeeds(values: readonly unknown[]): Need[] {
  return NEEDS.filter((need) => values.includes(need));
}

/** Stored profile; an invalid or missing value is an empty profile. */
export function getNeedsProfile(): Need[] {
  const raw = safeStorage.get(NEEDS_PROFILE_STORAGE_KEY);
  if (raw === null) return [];
  try {
    const value: unknown = JSON.parse(raw);
    return Array.isArray(value) ? canonicalNeeds(value) : [];
  } catch {
    return [];
  }
}

export function setNeedsProfile(needs: readonly Need[]): void {
  safeStorage.set(NEEDS_PROFILE_STORAGE_KEY, JSON.stringify(canonicalNeeds(needs)));
}

export function clearNeedsProfile(): void {
  safeStorage.remove(NEEDS_PROFILE_STORAGE_KEY);
}
