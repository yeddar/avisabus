import type { Alert } from '../../../shared/api/types';

/** Active alerts of this device, in every stop, by alert_id. */
export type AlertsState = { alerts: Record<string, Alert> };

export type ExpiryReason = 'PASSED' | 'NEXT_STOP' | 'TIMEOUT';

/** Messages of /ws/passenger (realtime_events design §3; alert_create, alert_cancel, alert_expiry). */
export type PassengerMessage =
  | { type: 'alerts.snapshot'; alerts: Alert[] }
  | { type: 'alert.registered' | 'alert.delivered'; alert: Alert }
  | { type: 'alert.expired'; alert_id: string; reason: ExpiryReason }
  | { type: 'alert.cancelled'; alert_id: string }
  | { type: 'ping' };

/** Changes made by this view itself: an alert created or cancelled with the API. */
export type LocalAction =
  { type: 'local.created'; alert: Alert } | { type: 'local.removed'; alert_id: string };

export const INITIAL_ALERTS_STATE: AlertsState = { alerts: {} };

const REASONS: readonly string[] = ['PASSED', 'NEXT_STOP', 'TIMEOUT'];
const STATUSES: readonly string[] = ['PENDING_DRIVER', 'DELIVERED'];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

const isString = (value: unknown): value is string => typeof value === 'string';

/** The fields of an alert that the interface uses, with the right types. */
function isAlert(value: unknown): value is Alert {
  return (
    isRecord(value) &&
    isString(value.alert_id) &&
    isString(value.stop_id) &&
    isString(value.line) &&
    isString(value.destination) &&
    isString(value.trip_id) &&
    isString(value.service_date) &&
    isString(value.status) &&
    STATUSES.includes(value.status) &&
    Array.isArray(value.needs) &&
    value.needs.every(isString)
  );
}

/**
 * A frame of /ws/passenger as a typed message, or null if it is not one (invalid JSON, unknown
 * type or missing fields): such frames are ignored.
 */
export function parsePassengerMessage(raw: unknown): PassengerMessage | null {
  if (!isString(raw)) return null;
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return null;
  }
  return toPassengerMessage(value);
}

/** Validates an already parsed message (also used for the GET /alerts/mine fallback). */
export function toPassengerMessage(value: unknown): PassengerMessage | null {
  if (!isRecord(value)) return null;
  switch (value.type) {
    case 'alerts.snapshot':
      return Array.isArray(value.alerts) && value.alerts.every(isAlert)
        ? (value as PassengerMessage)
        : null;
    case 'alert.registered':
    case 'alert.delivered':
      return isAlert(value.alert) ? (value as PassengerMessage) : null;
    case 'alert.expired':
      return isString(value.alert_id) && isString(value.reason) && REASONS.includes(value.reason)
        ? (value as PassengerMessage)
        : null;
    case 'alert.cancelled':
      return isString(value.alert_id) ? (value as PassengerMessage) : null;
    case 'ping':
      return { type: 'ping' };
    default:
      return null;
  }
}

function withAlert(state: AlertsState, alert: Alert): AlertsState {
  return { alerts: { ...state.alerts, [alert.alert_id]: alert } };
}

function without(state: AlertsState, alertId: string): AlertsState {
  if (!(alertId in state.alerts)) return state;
  const alerts = { ...state.alerts };
  delete alerts[alertId];
  return { alerts };
}

/** State after a message of the server or a local change (pure). */
export function alertsReducer(
  state: AlertsState,
  message: PassengerMessage | LocalAction,
): AlertsState {
  switch (message.type) {
    case 'alerts.snapshot':
      return { alerts: Object.fromEntries(message.alerts.map((a) => [a.alert_id, a])) };
    case 'alert.registered':
    case 'alert.delivered':
    case 'local.created':
      return withAlert(state, message.alert);
    case 'alert.expired':
    case 'alert.cancelled':
    case 'local.removed':
      return without(state, message.alert_id);
    case 'ping':
      return state;
  }
}

/** Alerts of `state` that `message` takes away (to move the focus out of their controls). */
export function removedAlerts(
  state: AlertsState,
  message: PassengerMessage | LocalAction,
): Alert[] {
  const next = alertsReducer(state, message);
  return Object.values(state.alerts).filter((alert) => !(alert.alert_id in next.alerts));
}
