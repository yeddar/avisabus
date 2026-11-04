import type { ReactNode } from 'react';
import { Trans, useTranslation } from 'react-i18next';

import type { Alert } from '../../../shared/api/types';
import { Button } from '../../../shared/ui/Button';
import { CheckIcon } from '../../../shared/ui/icons/CheckIcon';
import { useUiLanguage } from '../stop/useUiLanguage';
import { needsSummary } from './alertMessages';
import { useAlerts } from './AlertsProvider';

export interface AlertStatusProps {
  alert: Alert;
  /** Line and destination, when the box is not inside the card of its bus (AC-08). */
  title?: ReactNode;
}

/**
 * Status of an active request (passenger_alert_ui.AC-07, docs/design.md §5.8): accent-surface
 * box with a check icon, the status ("Parada solicitada." in bold), the needs indicated and
 * "Cancelar solicitud" (secondary, full width, 48 px), which cancels without confirmation (AC-09).
 */
export function AlertStatus({ alert, title }: AlertStatusProps) {
  const { t } = useTranslation();
  const language = useUiLanguage();
  const { cancel, statusRef } = useAlerts();
  const needs = needsSummary(alert.needs, language, t);

  return (
    <div
      ref={statusRef(alert.alert_id)}
      className="flex flex-col gap-3 rounded-[10px] border-2 border-accent bg-accent-surface p-3 text-base text-text"
    >
      <div className="flex gap-2.5">
        <CheckIcon className="mt-0.5 size-5 shrink-0 text-accent" />
        <div className="flex min-w-0 flex-col gap-1">
          {title}
          <p>
            <Trans
              i18nKey={alert.status === 'DELIVERED' ? 'alert.delivered' : 'alert.pending'}
              components={{ strong: <strong /> }}
            />
          </p>
          {needs !== null && <p className="text-text-muted">{needs}</p>}
        </div>
      </div>
      <Button className="min-h-12 w-full" onClick={() => void cancel(alert.alert_id)}>
        {t('alert.cancel')}
      </Button>
    </div>
  );
}
