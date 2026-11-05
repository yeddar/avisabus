import { Trans } from 'react-i18next';

import type { Arrival } from '../../../shared/api/types';
import { gtfsLang, useUiLanguage } from '../stop/useUiLanguage';
import { arrivalTripKey, tripKey, useAlerts } from './AlertsProvider';
import { AlertStatus } from './AlertStatus';

export interface OrphanAlertsProps {
  stopId: string;
  arrivals: Arrival[];
}

/**
 * Requests of this device at this stop whose bus is not (or no longer) among the arrivals in
 * the network (passenger_alert_ui.AC-08): shown above the list with their line, destination,
 * status and "Cancelar solicitud", since no card can hold them.
 */
export function OrphanAlerts({ stopId, arrivals }: OrphanAlertsProps) {
  const language = useUiLanguage();
  const { alertsAt } = useAlerts();
  const shown = new Set(arrivals.filter((arrival) => arrival.in_network).map(arrivalTripKey));
  const orphans = alertsAt(stopId).filter((alert) => !shown.has(tripKey(alert)));
  if (orphans.length === 0) return null;

  return (
    <div className="flex flex-col gap-3">
      {orphans.map((alert) => (
        <AlertStatus
          key={alert.alert_id}
          alert={alert}
          title={
            <p className="text-lg leading-[1.2] font-bold">
              <Trans
                i18nKey="alert.orphanTitle"
                values={{ line: alert.line, destination: alert.destination }}
                components={{ destination: <span lang={gtfsLang(language)} /> }}
              />
            </p>
          }
        />
      ))}
    </div>
  );
}
