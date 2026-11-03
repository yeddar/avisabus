import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';

import type { Arrival } from '../../../shared/api/types';
import { useAnnounce } from '../../../shared/ui/Announcer';
import { currentMinutes } from './countdown';
import { spokenDestination } from './destination';

/** Several buses arriving at once are announced in one message, one sentence each. */
const SENTENCE_SEPARATOR = '. ';

interface AnnouncementState {
  /** False until the first data have been seen. */
  initialised: boolean;
  /** Keys `${line}|${destination}|${trip_id ?? arrival_at}` already handled. */
  handled: Set<string>;
  /** Line|destination groups whose first arrival was "Llegando" in the previous evaluation. */
  arriving: Set<string>;
}

/** First arrival (API order) of each line and spoken destination. */
function firstOfEachGroup(arrivals: Arrival[]): Map<string, Arrival> {
  const firsts = new Map<string, Arrival>();
  for (const arrival of arrivals) {
    const group = `${arrival.line}|${spokenDestination(arrival)}`;
    if (!firsts.has(group)) firsts.set(group, arrival);
  }
  return firsts;
}

/**
 * Announces, politely and once, "Línea {line} hacia {destination} está llegando" when the first
 * arrival of a line and destination passes to "Llegando" (passenger_stop_view.AC-15, design §3).
 * Nothing else of the periodic refreshes is announced.
 *
 * - Only MINUTES arrivals can pass to "Llegando" (0 min, by the API or by the countdown);
 *   clock-time arrivals are always shown as HH:MM (AC-06).
 * - Buses already arriving when the data first appear are not announced: the list shows them.
 * - Without a vehicle, the key depends on `arrival_at`, which moves with every refresh; a group
 *   that stays "Llegando" from one evaluation to the next is the same bus and is not repeated.
 */
export function useArrivingAnnouncements(arrivals: Arrival[], now: Date): void {
  const { t } = useTranslation();
  const announce = useAnnounce();
  const state = useRef<AnnouncementState>({
    initialised: false,
    handled: new Set(),
    arriving: new Set(),
  });

  useEffect(() => {
    const current = state.current;
    const arrivingNow = new Set<string>();
    const messages: string[] = [];

    for (const [group, arrival] of firstOfEachGroup(arrivals)) {
      if (currentMinutes(arrival, now) !== 0) continue;
      arrivingNow.add(group);
      const key = `${group}|${arrival.vehicle?.trip_id ?? arrival.arrival_at}`;
      if (current.handled.has(key)) continue;
      current.handled.add(key);
      const sameBusStillArriving = arrival.vehicle === null && current.arriving.has(group);
      if (current.initialised && !sameBusStillArriving) {
        messages.push(
          t('stop.arriving', { line: arrival.line, destination: spokenDestination(arrival) }),
        );
      }
    }

    current.arriving = arrivingNow;
    current.initialised = true;
    if (messages.length > 0) announce(messages.join(SENTENCE_SEPARATOR), 'polite');
  }, [arrivals, now, t, announce]);
}
