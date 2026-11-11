import type { DriverView } from './types';

export interface FreshAlert {
  alertId: string;
  stopId: string;
}

/**
 * Alerts of `view` that were not in `seen` (driver_ui.AC-07), and the new set of seen ones. With
 * `initial` (first view after entering or reconnecting) everything is marked as seen silently.
 */
export function diffAlerts(
  seen: ReadonlySet<string>,
  view: DriverView,
  initial: boolean,
): { seen: Set<string>; fresh: FreshAlert[] } {
  const next = new Set(seen);
  const fresh: FreshAlert[] = [];
  for (const stop of view.stops) {
    for (const alertId of stop.alert_ids) {
      if (!seen.has(alertId) && !initial) fresh.push({ alertId, stopId: stop.stop_id });
      next.add(alertId);
    }
  }
  return { seen: next, fresh };
}
