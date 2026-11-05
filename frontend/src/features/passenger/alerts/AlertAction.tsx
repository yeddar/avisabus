import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import type { Arrival } from '../../../shared/api/types';
import { Button } from '../../../shared/ui/Button';
import { HandIcon } from '../../../shared/ui/icons/HandIcon';
import { spokenDestination } from '../stop/destination';
import { arrivalTripKey, useAlerts } from './AlertsProvider';
import { RequestDialog } from './RequestDialog';

export interface AlertActionProps {
  arrival: Arrival;
  now: Date;
  scheduled: boolean;
  /** Stop of the view and token of its QR, sent with the request. */
  stopId: string;
  token: string;
  /** The device already has an active request for another bus of this line here (RF-19). */
  otherBus: boolean;
}

/**
 * Request action of an arrival that admits it (passenger_alert_ui.AC-03): the primary
 * "Solicitar" button, named with the line and spoken destination, or, if another bus of the
 * line is already requested at this stop, a note instead of the button (docs/design.md §5.8).
 */
export function AlertAction({
  arrival,
  now,
  scheduled,
  stopId,
  token,
  otherBus,
}: AlertActionProps) {
  const { t } = useTranslation();
  const { requestButtonRef } = useAlerts();
  const [open, setOpen] = useState(false);
  const button = useRef<HTMLButtonElement | null>(null);
  const key = arrivalTripKey(arrival);
  const { vehicle, direction_id: directionId } = arrival;

  if (otherBus) {
    return (
      <p className="flex flex-1 items-center text-[0.9375rem] text-text-muted">
        {t('alert.otherBus')}
      </p>
    );
  }

  // can_alert implies a vehicle and a direction (alert_create.AC-01); without them, no request.
  if (vehicle === null || directionId === null || key === null) return null;
  const register = requestButtonRef(key);

  return (
    <>
      <Button
        ref={(element) => {
          button.current = element;
          register(element);
        }}
        onClick={() => setOpen(true)}
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
      {open && (
        <RequestDialog
          arrival={arrival}
          request={{
            stop_id: stopId,
            token,
            line: arrival.line,
            direction_id: directionId,
            trip_id: vehicle.trip_id,
            service_date: vehicle.service_date,
          }}
          now={now}
          scheduled={scheduled}
          onDismiss={() => {
            setOpen(false);
            button.current?.focus();
          }}
        />
      )}
    </>
  );
}
