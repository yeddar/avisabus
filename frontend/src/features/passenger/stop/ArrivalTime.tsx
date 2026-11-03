import { Trans, useTranslation } from 'react-i18next';

import type { Arrival } from '../../../shared/api/types';
import { formatClockTime } from '../../../shared/i18n/format';
import { currentMinutes } from './countdown';
import { useUiLanguage } from './useUiLanguage';

export interface ArrivalTimeProps {
  arrival: Arrival;
  /** Server time (useServerNow), to count MINUTES down between responses. */
  now: Date;
  /** The data come from the scheduled timetable. */
  scheduled: boolean;
}

/**
 * Arrival time as shown on screen (passenger_stop_view.AC-06, docs/design.md §3): "N min" with
 * the figure at 30 px, "Llegando" or the clock time at 24 px, and "programado" below when the
 * data are scheduled (AC-09).
 */
export function ArrivalTime({ arrival, now, scheduled }: ArrivalTimeProps) {
  const { t } = useTranslation();
  const language = useUiLanguage();
  const minutes = currentMinutes(arrival, now);

  let main;
  if (minutes === null) {
    main = (
      <span className="text-2xl font-bold">{formatClockTime(arrival.arrival_at, language)}</span>
    );
  } else if (minutes === 0) {
    main = <span className="text-2xl font-bold">{t('time.arriving')}</span>;
  } else {
    main = (
      <span className="font-bold whitespace-nowrap">
        <Trans
          i18nKey="stop.minutes"
          values={{ value: minutes }}
          components={{
            number: <span className="text-[1.875rem] leading-none" />,
            unit: <span className="text-lg" />,
          }}
        />
      </span>
    );
  }

  return (
    <span className="flex shrink-0 flex-col items-end text-right">
      {main}
      {scheduled && (
        <span className="text-[0.8125rem] text-text-muted">{t('stop.scheduledSuffix')}</span>
      )}
    </span>
  );
}
