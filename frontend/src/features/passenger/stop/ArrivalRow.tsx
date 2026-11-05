import type { ReactNode } from 'react';
import { Trans, useTranslation } from 'react-i18next';

import type { Arrival } from '../../../shared/api/types';
import { GtfsText } from '../../../shared/i18n/GtfsText';
import { MapIcon } from '../../../shared/ui/icons/MapIcon';
import { LinkButton } from '../../../shared/ui/LinkButton';
import { AlertAction } from '../alerts/AlertAction';
import { arrivalTripKey, tripKey, useOptionalAlerts } from '../alerts/AlertsProvider';
import { AlertStatus } from '../alerts/AlertStatus';
import { ArrivalTime } from './ArrivalTime';
import { spokenDestination, visibleDestination } from './destination';
import { LineBadge } from './LineBadge';
import { OccupancyInfo } from './OccupancyInfo';
import { spokenArrivalTime } from './spokenTime';
import { gtfsLang, useUiLanguage } from './useUiLanguage';

export interface ArrivalRowProps {
  arrival: Arrival;
  now: Date;
  scheduled: boolean;
  /** Stop of the view and token of its QR, kept in the link to the map. */
  stopId: string;
  token: string;
}

/** Map of the line and direction (passenger_map_view.AC-01): route of passenger_map_view. */
export function mapPath(stopId: string, line: string, directionId: number, token: string): string {
  const path = [stopId, 'map', line, String(directionId)].map(encodeURIComponent).join('/');
  return `/p/${path}?t=${encodeURIComponent(token)}`;
}

/**
 * Arrival card (docs/design.md §5.3). Screen readers get one full sentence
 * (passenger_stop_view.AC-05); the visual content is hidden from them so it is not read twice.
 * Arrivals outside the network show only their time (AC-08). Arrivals in the network with a
 * resolved direction link to their map (passenger_map_view.AC-01). Inside the stop view (with
 * the alerts context), row 3 also holds "Solicitar" (passenger_alert_ui.AC-03), and the card of
 * the requested bus shows the status of the request under "Ver en el mapa" (AC-07).
 */
export function ArrivalRow({ arrival, now, scheduled, stopId, token }: ArrivalRowProps) {
  const { t } = useTranslation();
  const language = useUiLanguage();
  const alerts = useOptionalAlerts();
  // The request of this device for this line at this stop (RF-19) and whether it is this bus.
  const lineAlert = alerts?.alertFor(stopId, arrival.line) ?? null;
  const ownTrip = arrivalTripKey(arrival);
  const ownAlert =
    lineAlert !== null && ownTrip !== null && tripKey(lineAlert) === ownTrip ? lineAlert : null;

  const time = spokenArrivalTime(arrival, now, scheduled, t, language);

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
      {arrival.in_network && (
        <ActionsRow
          map={
            arrival.direction_id === null ? null : (
              <LinkButton
                to={mapPath(stopId, arrival.line, arrival.direction_id, token)}
                aria-label={t('stop.viewOnMapLabel', {
                  line: arrival.line,
                  destination: spokenDestination(arrival),
                })}
                icon={<MapIcon className="size-[18px]" />}
                className="min-h-12 flex-1"
              >
                {t('stop.viewOnMap')}
              </LinkButton>
            )
          }
          request={
            alerts !== null && arrival.can_alert && ownAlert === null ? (
              <AlertAction
                arrival={arrival}
                now={now}
                scheduled={scheduled}
                stopId={stopId}
                token={token}
                otherBus={lineAlert !== null}
              />
            ) : null
          }
          status={ownAlert === null ? null : <AlertStatus alert={ownAlert} />}
        />
      )}
    </li>
  );
}

interface ActionsRowProps {
  map: ReactNode;
  request: ReactNode;
  status: ReactNode;
}

/**
 * Row 3 of the card (docs/design.md §5.3, §5.8): "Ver en el mapa" and "Solicitar" at equal
 * widths, 48 px high, each full width while alone; with an active request, the status box
 * replaces the row and "Ver en el mapa" stays above it.
 */
function ActionsRow({ map, request, status }: ActionsRowProps) {
  if (status !== null) {
    return (
      <div className="mt-3 flex flex-col gap-3">
        {map !== null && <div className="flex">{map}</div>}
        {status}
      </div>
    );
  }
  if (map === null && request === null) return null;
  return (
    <div className="mt-3 flex gap-3">
      {map}
      {request}
    </div>
  );
}
