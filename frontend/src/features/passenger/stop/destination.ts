import type { Arrival } from '../../../shared/api/types';

/**
 * On screen, the SAE text (what the passenger reads on the bus sign); with the scheduled
 * timetable there is none, so the GTFS headsign (passenger_stop_view.AC-05).
 */
export function visibleDestination(a: Arrival): string {
  return a.sae_destination ?? a.destination;
}

/** For screen readers, always `destination` (GTFS headsign when the direction is resolved). */
export function spokenDestination(a: Arrival): string {
  return a.destination;
}
