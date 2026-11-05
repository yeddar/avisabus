import type { TFunction } from 'i18next';

import type { Arrival } from '../../../shared/api/types';
import { formatClockTime, formatMinutes } from '../../../shared/i18n/format';
import type { Language } from '../../../shared/i18n/languages';
import { currentMinutes } from './countdown';

/**
 * Time of an arrival as words ("llega en 4 minutos", "está llegando", "llega a las 08:52",
 * with "según el horario programado" for the scheduled timetable; passenger_stop_view.AC-05).
 */
export function spokenArrivalTime(
  arrival: Arrival,
  now: Date,
  scheduled: boolean,
  t: TFunction,
  language: Language,
): string {
  const minutes = currentMinutes(arrival, now);
  let time: string;
  if (minutes === null) {
    time = t('stop.arrivesAt', { time: formatClockTime(arrival.arrival_at, language) });
  } else if (minutes === 0) {
    time = t('stop.arrivingNow');
  } else {
    time = t('stop.arrivesIn', { duration: formatMinutes(minutes, language).long });
  }
  return scheduled ? t('stop.scheduledTime', { time }) : time;
}
