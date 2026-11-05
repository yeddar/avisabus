import type { TFunction } from 'i18next';

import type { Need } from '../../../shared/api/types';
import type { Language } from '../../../shared/i18n/languages';
import type { AlertsState, PassengerMessage } from './alertsReducer';

/**
 * Polite announcement for a message of /ws/passenger (passenger_alert_ui.AC-11), or null when
 * it changes the state silently (registered, cancelled, snapshot). `state` is the state
 * *before* the message: an expired alert is only known (with its line) there.
 */
export function eventAnnouncement(
  message: PassengerMessage,
  state: AlertsState,
  t: TFunction,
): string | null {
  switch (message.type) {
    case 'alert.delivered':
      return t('alert.event.delivered', { line: message.alert.line });
    case 'alert.expired': {
      const alert = state.alerts[message.alert_id];
      if (alert === undefined) return null;
      return t('alert.event.expired', {
        line: alert.line,
        reason: t(`alert.event.reason.${message.reason}`),
      });
    }
    default:
      return null;
  }
}

/** "Has indicado: rampa y asiento" with the list format of the language; null without needs. */
export function needsSummary(
  needs: readonly Need[],
  language: Language,
  t: TFunction,
): string | null {
  if (needs.length === 0) return null;
  const list = new Intl.ListFormat(language, { style: 'long', type: 'conjunction' }).format(
    needs.map((need) => t(`needs.short.${need}`)),
  );
  return t('alert.youIndicated', { needs: list });
}
