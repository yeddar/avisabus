import type { Arrival } from '../../../shared/api/types';

const MINUTE_MS = 60_000;

/**
 * Minutes left for a MINUTES arrival at server time `now` (passenger_stop_view.AC-13): the time
 * to `arrival_at` rounded up, never below 0 nor above the minutes given by the API. Null for
 * CLOCK_TIME arrivals, which are shown as a clock time.
 */
export function currentMinutes(arrival: Arrival, now: Date): number | null {
  if (arrival.kind !== 'MINUTES') return null;
  const left = Math.max(0, Math.ceil((Date.parse(arrival.arrival_at) - now.getTime()) / MINUTE_MS));
  return arrival.minutes === null ? left : Math.min(arrival.minutes, left);
}
