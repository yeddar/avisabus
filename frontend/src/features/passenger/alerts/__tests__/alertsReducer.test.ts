import { describe, expect, it } from 'vitest';

import { alert70, alertFixture } from '../../../../test/fixtures/alerts';
import {
  type AlertsState,
  alertsReducer,
  parsePassengerMessage,
  removedAlerts,
} from '../alertsReducer';

const A93 = alertFixture();
const A70 = alert70();
const EMPTY: AlertsState = { alerts: {} };
const BOTH: AlertsState = { alerts: { [A93.alert_id]: A93, [A70.alert_id]: A70 } };

describe('alertsReducer', () => {
  it('[passenger_alert_ui.AC-10] a snapshot replaces the whole state', () => {
    const state = alertsReducer(BOTH, { type: 'alerts.snapshot', alerts: [A70] });

    expect(state).toEqual({ alerts: { [A70.alert_id]: A70 } });
  });

  it('[passenger_alert_ui.AC-11] registered and delivered add or update the alert', () => {
    const registered = alertsReducer(EMPTY, { type: 'alert.registered', alert: A93 });
    expect(registered.alerts[A93.alert_id]?.status).toBe('PENDING_DRIVER');

    const delivered = alertsReducer(registered, {
      type: 'alert.delivered',
      alert: { ...A93, status: 'DELIVERED' },
    });
    expect(delivered.alerts[A93.alert_id]?.status).toBe('DELIVERED');
    expect(Object.keys(delivered.alerts)).toEqual([A93.alert_id]);
  });

  it('[passenger_alert_ui.AC-11] expired and cancelled remove the alert', () => {
    const expired = alertsReducer(BOTH, {
      type: 'alert.expired',
      alert_id: A93.alert_id,
      reason: 'PASSED',
    });
    expect(Object.keys(expired.alerts)).toEqual([A70.alert_id]);

    const cancelled = alertsReducer(expired, { type: 'alert.cancelled', alert_id: A70.alert_id });
    expect(cancelled.alerts).toEqual({});
  });

  it('[passenger_alert_ui.AC-11] removing an unknown alert changes nothing', () => {
    expect(alertsReducer(BOTH, { type: 'alert.cancelled', alert_id: 'nope' })).toBe(BOTH);
  });

  it('[passenger_alert_ui.AC-05] [passenger_alert_ui.AC-09] local creation and removal', () => {
    const created = alertsReducer(EMPTY, { type: 'local.created', alert: A93 });
    expect(created.alerts[A93.alert_id]).toEqual(A93);

    expect(alertsReducer(created, { type: 'local.removed', alert_id: A93.alert_id })).toEqual(
      EMPTY,
    );
  });

  it('[passenger_alert_ui.AC-11] ping leaves the state as it is', () => {
    expect(alertsReducer(BOTH, { type: 'ping' })).toBe(BOTH);
  });
});

describe('removedAlerts', () => {
  it('[passenger_alert_ui.AC-11] lists the alerts a message takes away', () => {
    expect(removedAlerts(BOTH, { type: 'alert.cancelled', alert_id: A70.alert_id })).toEqual([A70]);
    expect(
      removedAlerts(BOTH, { type: 'alert.expired', alert_id: A93.alert_id, reason: 'TIMEOUT' }),
    ).toEqual([A93]);
    expect(removedAlerts(BOTH, { type: 'alerts.snapshot', alerts: [A93] })).toEqual([A70]);
    expect(removedAlerts(BOTH, { type: 'alert.registered', alert: A93 })).toEqual([]);
    expect(removedAlerts(EMPTY, { type: 'alert.cancelled', alert_id: A70.alert_id })).toEqual([]);
  });
});

describe('parsePassengerMessage', () => {
  it('[passenger_alert_ui.AC-10] accepts the messages of the passenger protocol', () => {
    const messages = [
      { type: 'alerts.snapshot', alerts: [A93] },
      { type: 'alert.registered', alert: A93 },
      { type: 'alert.delivered', alert: A93 },
      { type: 'alert.expired', alert_id: 'a', reason: 'NEXT_STOP', stop_id: '508', line: '93' },
      { type: 'alert.cancelled', alert_id: 'a' },
      { type: 'ping' },
    ];

    for (const message of messages) {
      expect(parsePassengerMessage(JSON.stringify(message))).toEqual(message);
    }
  });

  it.each([
    ['not JSON', '{oops'],
    ['not an object', '[1]'],
    ['an unknown type', '{"type":"hello"}'],
    ['a snapshot without a list', '{"type":"alerts.snapshot","alerts":{}}'],
    ['an alert without id', '{"type":"alert.delivered","alert":{"line":"93"}}'],
    ['an unknown reason', '{"type":"alert.expired","alert_id":"a","reason":"SOON"}'],
    ['a cancellation without id', '{"type":"alert.cancelled"}'],
    ['a binary frame', new ArrayBuffer(2)],
  ])('[passenger_alert_ui.AC-10] rejects %s', (_, raw) => {
    expect(parsePassengerMessage(raw)).toBeNull();
  });
});
