import { useTranslation } from 'react-i18next';

import type { Arrival } from '../../../shared/api/types';
import { Button } from '../../../shared/ui/Button';
import { HandIcon } from '../../../shared/ui/icons/HandIcon';
import { spokenDestination } from '../stop/destination';
import { arrivalTripKey, useAlerts } from './AlertsProvider';

export interface AlertActionProps {
  arrival: Arrival;
  /** The device already has an active request for another bus of this line here (RF-19). */
  otherBus: boolean;
}

/**
 * Request action of an arrival that admits it (passenger_alert_ui.AC-03): the primary
 * "Solicitar" button, named with the line and spoken destination, or, if another bus of the
 * line is already requested at this stop, a note instead of the button (docs/design.md §5.8).
 */
export function AlertAction({ arrival, otherBus }: AlertActionProps) {
  const { t } = useTranslation();
  const { requestButtonRef } = useAlerts();
  const key = arrivalTripKey(arrival);

  if (otherBus) {
    return (
      <p className="flex flex-1 items-center text-[0.9375rem] text-text-muted">
        {t('alert.otherBus')}
      </p>
    );
  }

  return (
    <Button
      ref={key === null ? undefined : requestButtonRef(key)}
      variant="primary"
      icon={<HandIcon className="size-[18px]" />}
      aria-label={t('alert.requestLabel', {
        line: arrival.line,
        destination: spokenDestination(arrival),
      })}
      className="min-h-12 flex-1"
    >
      {t('alert.request')}
    </Button>
  );
}
