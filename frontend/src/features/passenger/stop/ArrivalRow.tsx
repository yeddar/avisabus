import { Trans, useTranslation } from 'react-i18next';

import type { Arrival } from '../../../shared/api/types';
import { formatClockTime, formatMinutes } from '../../../shared/i18n/format';
import { GtfsText } from '../../../shared/i18n/GtfsText';
import { ArrivalTime } from './ArrivalTime';
import { currentMinutes } from './countdown';
import { spokenDestination, visibleDestination } from './destination';
import { LineBadge } from './LineBadge';
import { OccupancyInfo } from './OccupancyInfo';
import { gtfsLang, useUiLanguage } from './useUiLanguage';

export interface ArrivalRowProps {
  arrival: Arrival;
  now: Date;
  scheduled: boolean;
}

/**
 * Arrival card (docs/design.md §5.3). Screen readers get one full sentence
 * (passenger_stop_view.AC-05); the visual content is hidden from them so it is not read twice.
 * Arrivals outside the network show only their time (AC-08).
 */
export function ArrivalRow({ arrival, now, scheduled }: ArrivalRowProps) {
  const { t } = useTranslation();
  const language = useUiLanguage();
  const minutes = currentMinutes(arrival, now);

  let time: string;
  if (minutes === null) {
    time = t('stop.arrivesAt', { time: formatClockTime(arrival.arrival_at, language) });
  } else if (minutes === 0) {
    time = t('stop.arrivingNow');
  } else {
    time = t('stop.arrivesIn', { duration: formatMinutes(minutes, language).long });
  }
  if (scheduled) time = t('stop.scheduledTime', { time });

  let occupancy: string | null = null;
  if (arrival.in_network) {
    occupancy =
      arrival.occupancy === null
        ? t('occupancy.spoken.unavailable')
        : t('occupancy.spokenWithSeats', {
            level: t(`occupancy.spoken.${arrival.occupancy.level}`),
            seats: t(arrival.occupancy.has_free_seats ? 'occupancy.seatsYes' : 'occupancy.seatsNo'),
          });
  }

  return (
    <li className="rounded-[14px] border border-border bg-surface p-3.5">
      <span className="sr-only">
        <Trans
          i18nKey={occupancy === null ? 'stop.rowLabelNoOccupancy' : 'stop.rowLabel'}
          values={{
            line: arrival.line,
            destination: spokenDestination(arrival),
            time,
            ...(occupancy === null ? {} : { occupancy }),
          }}
          components={{ destination: <span lang={gtfsLang(language)} /> }}
        />
      </span>
      <div aria-hidden="true" className="flex flex-col gap-3">
        <div className="flex items-start gap-3">
          <LineBadge
            line={arrival.line}
            color={arrival.line_color}
            textColor={arrival.line_text_color}
          />
          <div className="flex min-w-0 flex-1 flex-col">
            <span className="text-sm text-text-muted">{t('stop.towards')}</span>
            <span className="text-lg leading-[1.2] font-bold break-words">
              <GtfsText>{visibleDestination(arrival)}</GtfsText>
            </span>
          </div>
          <ArrivalTime arrival={arrival} now={now} scheduled={scheduled} />
        </div>
        {arrival.in_network && <OccupancyInfo occupancy={arrival.occupancy} />}
      </div>
    </li>
  );
}
