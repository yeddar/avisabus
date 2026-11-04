import { useTranslation } from 'react-i18next';

import type { Arrival, ArrivalSource } from '../../../shared/api/types';
import { ArrivalRow } from './ArrivalRow';

export interface ArrivalsListProps {
  arrivals: Arrival[];
  source: ArrivalSource;
  now: Date;
  /** Stop of the view and token of its QR, for the links to the map. */
  stopId: string;
  token: string;
}

/** Arrivals in the order given by the API (passenger_stop_view.AC-05), or the empty state (AC-10). */
export function ArrivalsList({ arrivals, source, now, stopId, token }: ArrivalsListProps) {
  const { t } = useTranslation();

  if (arrivals.length === 0) {
    return <p className="text-lg">{t('stop.empty')}</p>;
  }

  return (
    // role="list" keeps the list semantics in Safari/VoiceOver, which drops them with list-style: none.
    // eslint-disable-next-line jsx-a11y/no-redundant-roles
    <ul role="list" className="flex flex-col gap-3">
      {arrivals.map((arrival, index) => (
        <ArrivalRow
          key={`${index}|${arrival.line}|${arrival.destination}|${arrival.arrival_at}`}
          arrival={arrival}
          now={now}
          scheduled={source === 'SCHEDULED'}
          stopId={stopId}
          token={token}
        />
      ))}
    </ul>
  );
}
