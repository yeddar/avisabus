import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';

import type { PositionResponse } from '../../../shared/api/types';
import { useAnnounce } from '../../../shared/ui/Announcer';

type Milestone = 'ONE_STOP' | 'ARRIVING';

const MESSAGES: Record<Milestone, 'map.announceOneStop' | 'map.announceArriving'> = {
  ONE_STOP: 'map.announceOneStop',
  ARRIVING: 'map.announceArriving',
};

/** Milestone that the answer shows, if any: AT_STOP, or the passenger's stop is the next one. */
function milestoneOf(p: PositionResponse): Milestone | null {
  if (p.status === 'AT_STOP') return 'ARRIVING';
  return p.position?.stops_away === 0 ? 'ONE_STOP' : null;
}

/**
 * Polite announcements of the bus approaching (passenger_map_view.AC-06, design §3): when
 * `stops_away` passes to 0 and when the status passes to AT_STOP, each once per trip
 * (`vehicle.trip_id`). Nothing else of the refreshes is announced.
 *
 * - What the first data already show is not announced: the summary says it.
 * - A bus that reaches AT_STOP is not announced afterwards as "en la siguiente".
 * - An estimate that goes back (the SAE delays the bus) does not repeat a milestone.
 */
export function useProximityAnnouncements(position: PositionResponse | undefined): void {
  const { t } = useTranslation();
  const announce = useAnnounce();
  const state = useRef({ initialised: false, handled: new Set<string>() });

  useEffect(() => {
    if (position === undefined) return;
    const current = state.current;
    const initialised = current.initialised;
    current.initialised = true;
    const tripId = position.vehicle?.trip_id;
    const milestone = milestoneOf(position);
    if (tripId === undefined || milestone === null) return;

    const key = `${tripId}|${milestone}`;
    if (current.handled.has(key)) return;
    current.handled.add(key);
    if (milestone === 'ARRIVING') current.handled.add(`${tripId}|ONE_STOP`);
    if (initialised) announce(t(MESSAGES[milestone]), 'polite');
  }, [position, t, announce]);
}
