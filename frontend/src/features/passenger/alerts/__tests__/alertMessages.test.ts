import { describe, expect, it } from 'vitest';

import { alertFixture } from '../../../../test/fixtures/alerts';
import { initI18n } from '../../../../shared/i18n/i18n';
import { eventAnnouncement, needsSummary } from '../alertMessages';
import type { AlertsState } from '../alertsReducer';

const A93 = alertFixture();
const STATE: AlertsState = { alerts: { [A93.alert_id]: A93 } };

describe('eventAnnouncement', () => {
  it.each([
    ['es', 'El conductor de la línea 93 ha recibido tu solicitud'],
    ['ca', 'El conductor de la línia 93 ha rebut la teua sol·licitud'],
  ] as const)('[passenger_alert_ui.AC-11] alert.delivered (%s)', (language, expected) => {
    const { t } = initI18n({ language });

    expect(
      eventAnnouncement(
        { type: 'alert.delivered', alert: { ...A93, status: 'DELIVERED' } },
        STATE,
        t,
      ),
    ).toBe(expected);
  });

  it.each([
    [
      'es',
      'PASSED',
      'Tu solicitud de la línea 93 ha terminado: el autobús ha pasado por la parada',
    ],
    [
      'es',
      'NEXT_STOP',
      'Tu solicitud de la línea 93 ha terminado: el autobús ya ha llegado a la parada siguiente',
    ],
    ['es', 'TIMEOUT', 'Tu solicitud de la línea 93 ha terminado: han pasado 30 minutos'],
    [
      'ca',
      'PASSED',
      "La teua sol·licitud de la línia 93 ha acabat: l'autobús ha passat per la parada",
    ],
    [
      'ca',
      'NEXT_STOP',
      "La teua sol·licitud de la línia 93 ha acabat: l'autobús ja ha arribat a la parada següent",
    ],
    ['ca', 'TIMEOUT', 'La teua sol·licitud de la línia 93 ha acabat: han passat 30 minuts'],
  ] as const)('[passenger_alert_ui.AC-11] alert.expired (%s, %s)', (language, reason, expected) => {
    const { t } = initI18n({ language });

    expect(
      eventAnnouncement({ type: 'alert.expired', alert_id: A93.alert_id, reason }, STATE, t),
    ).toBe(expected);
  });

  it('[passenger_alert_ui.AC-11] says nothing for registered, cancelled, snapshot and ping', () => {
    const { t } = initI18n({ language: 'es' });

    expect(eventAnnouncement({ type: 'alert.registered', alert: A93 }, STATE, t)).toBeNull();
    expect(
      eventAnnouncement({ type: 'alert.cancelled', alert_id: A93.alert_id }, STATE, t),
    ).toBeNull();
    expect(eventAnnouncement({ type: 'alerts.snapshot', alerts: [] }, STATE, t)).toBeNull();
    expect(eventAnnouncement({ type: 'ping' }, STATE, t)).toBeNull();
  });

  it('[passenger_alert_ui.AC-11] says nothing when an unknown alert expires (its line is unknown)', () => {
    const { t } = initI18n({ language: 'es' });

    expect(
      eventAnnouncement({ type: 'alert.expired', alert_id: 'other', reason: 'PASSED' }, STATE, t),
    ).toBeNull();
  });
});

describe('needsSummary', () => {
  it.each([
    ['es', ['RAMP', 'SEAT'], 'Has indicado: rampa y asiento'],
    ['ca', ['RAMP', 'SEAT'], 'Has indicat: rampa i seient'],
    [
      'es',
      ['RAMP', 'EXTRA_TIME', 'VISUAL'],
      'Has indicado: rampa, más tiempo y discapacidad visual',
    ],
    ['es', ['SEAT'], 'Has indicado: asiento'],
  ] as const)(
    '[passenger_alert_ui.AC-07] lists the needs with Intl.ListFormat (%s, %j)',
    (language, needs, expected) => {
      const { t } = initI18n({ language });

      expect(needsSummary([...needs], language, t)).toBe(expected);
    },
  );

  it('[passenger_alert_ui.AC-07] is null without needs', () => {
    const { t } = initI18n({ language: 'es' });

    expect(needsSummary([], 'es', t)).toBeNull();
  });
});
