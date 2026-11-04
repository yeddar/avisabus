import type { TFunction } from 'i18next';

import type { PositionArrival, PositionResponse } from '../../../shared/api/types';
import { formatClockTime, formatDistance, formatMinutes } from '../../../shared/i18n/format';
import type { Language } from '../../../shared/i18n/languages';
import { currentMinutes } from '../stop/countdown';

/**
 * Text summary of the bus position (passenger_map_view.AC-04) and its badge (AC-05).
 *
 * `text` is a sentence with two inline marks, written by the translations: `<strong>…</strong>`
 * for the distance, the stops and the time (docs/design.md §5.7) and `<name>…</name>` for GTFS
 * names, which are shown in Valencian (frontend_i18n.AC-06). `summaryParts` splits it for
 * rendering and `summaryPlainText` removes the marks.
 */
export type Summary = { text: string; badge: 'estimated' | 'scheduled' };

export type SummaryPart = { kind: 'text' | 'strong' | 'name'; text: string };

const MARK = /<(strong|name)>(.*?)<\/\1>/g;

/** Plain text and marked parts of a summary text, in order. */
export function summaryParts(text: string): SummaryPart[] {
  const parts: SummaryPart[] = [];
  let last = 0;
  for (const match of text.matchAll(MARK)) {
    if (match.index > last) parts.push({ kind: 'text', text: text.slice(last, match.index) });
    parts.push({ kind: match[1] as 'strong' | 'name', text: match[2] ?? '' });
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push({ kind: 'text', text: text.slice(last) });
  return parts;
}

export function summaryPlainText(text: string): string {
  return summaryParts(text)
    .map((part) => part.text)
    .join('');
}

/** Valencian elides "de" before a vowel or a silent h ("d'Avinguda del Cid"). */
const ELIDES = /^h?[aeiouàáèéíïòóúü]/i;

/** {llegada}: the rule of passenger_stop_view.AC-06 with the countdown of AC-13. */
function arrivalSentence(
  arrival: PositionArrival,
  t: TFunction,
  lang: Language,
  now: Date,
): string {
  const minutes = currentMinutes(arrival, now);
  if (minutes === null) {
    return t('map.arrivesAt', { time: formatClockTime(arrival.arrival_at, lang) });
  }
  if (minutes === 0) return t('map.arrivingNow');
  return t('map.arrivesIn', { duration: formatMinutes(minutes, lang).long });
}

function unavailable(reason: 'map.reasonNoArrival' | 'map.reasonNoVehicle', t: TFunction): string {
  return `${t('map.unavailable')} ${t(reason)}`;
}

/**
 * Summary for a position answer. `firstStop` is the name of the first stop of the shape
 * (`shape.stops[0]`), or null while the shape is not available: in NOT_STARTED the API's
 * `next_stop` is the second stop of the trip (position_estimation.AC-08), so it is not used.
 * `now` is the server time (useServerNow).
 */
export function buildSummary(
  p: PositionResponse,
  firstStop: string | null,
  t: TFunction,
  lang: Language,
  now: Date,
): Summary {
  const badge = p.source === 'SCHEDULED' ? 'scheduled' : 'estimated';
  const { position, arrival } = p;

  if (p.status === 'AT_STOP') return { text: t('map.atStop'), badge };
  if (p.status === 'NO_ARRIVAL') return { text: unavailable('map.reasonNoArrival', t), badge };
  // NO_VEHICLE, or an inconsistent answer without the data to describe the bus.
  if (p.status === 'NO_VEHICLE' || position === null || arrival === null) {
    return { text: unavailable('map.reasonNoVehicle', t), badge };
  }

  const when = arrivalSentence(arrival, t, lang, now);
  if (p.status === 'NOT_STARTED') {
    const text =
      firstStop === null
        ? t('map.notStartedUnknown', { arrival: when })
        : t('map.notStarted', {
            stop: firstStop,
            arrival: when,
            context: ELIDES.test(firstStop) ? 'elided' : undefined,
          });
    return { text, badge };
  }

  const stops =
    position.stops_away === 0
      ? t('map.nextIsYours')
      : t('map.stopsAway', { count: position.stops_away });
  return {
    text: t('map.enRoute', {
      distance: formatDistance(position.distance_to_stop_m, lang),
      stops,
      next: position.next_stop.name,
      arrival: when,
    }),
    badge,
  };
}
