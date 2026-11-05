import {
  createContext,
  type ReactNode,
  type RefObject,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useTranslation } from 'react-i18next';

import { ApiError, apiSend } from '../../../shared/api/client';
import type {
  Alert,
  Arrival,
  CreateAlertRequest,
  MyAlertsResponse,
} from '../../../shared/api/types';
import { useOnline } from '../../../shared/hooks/useOnline';
import { usePassengerSocket } from '../../../shared/ws/usePassengerSocket';
import { useAnnounce } from '../../../shared/ui/Announcer';
import { eventAnnouncement } from './alertMessages';
import {
  type AlertsState,
  INITIAL_ALERTS_STATE,
  type LocalAction,
  type PassengerMessage,
  alertsReducer,
  removedAlerts,
  toPassengerMessage,
} from './alertsReducer';

/** While /ws/passenger is down, GET /alerts/mine every 30 s (passenger_alert_ui.AC-10). */
export const FALLBACK_POLL_MS = 30_000;

export type CreateAlertInput = CreateAlertRequest;
export type CreateError = 'gone' | 'rate' | 'notFound' | 'network';
export type CreateOutcome = 'ok' | { error: CreateError; retryAfterS?: number | null };
export type CancelOutcome = 'ok' | 'gone' | 'network';

/** A card and its alert are the same bus: same trip on the same service day (design §3). */
export function tripKey(trip: { trip_id: string; service_date: string }): string {
  return `${trip.trip_id}|${trip.service_date}`;
}

export function arrivalTripKey(arrival: Arrival): string | null {
  return arrival.vehicle === null ? null : tripKey(arrival.vehicle);
}

type FocusTarget = { target: 'cancel'; alertId: string } | { target: 'request'; tripKey: string };

export interface AlertsContextValue {
  /** Alert of this device at that stop and line (at most one, RF-19). */
  alertFor(stopId: string, line: string): Alert | null;
  /** Alerts of this device at that stop. */
  alertsAt(stopId: string): Alert[];
  create(input: CreateAlertInput): Promise<CreateOutcome>;
  cancel(alertId: string): Promise<CancelOutcome>;
  connected: boolean;
  /** Ref of the "Solicitar" button of a card, to give it the focus back (design §3). */
  requestButtonRef(key: string): (element: HTMLButtonElement | null) => void;
  /** Ref of the AlertStatus box of an alert (its "Cancelar solicitud" is the only button). */
  statusRef(alertId: string): (element: HTMLElement | null) => void;
}

const AlertsContext = createContext<AlertsContextValue | null>(null);

function createError(error: unknown): Exclude<CreateOutcome, 'ok'> {
  if (!(error instanceof ApiError)) return { error: 'network' };
  switch (error.status) {
    case 422:
      return { error: 'gone' };
    case 429:
      return { error: 'rate', retryAfterS: error.retryAfterS };
    case 404:
      return { error: 'notFound' };
    default:
      return { error: 'network' };
  }
}

export interface AlertsProviderProps {
  children: ReactNode;
  /** Where the focus goes when the control that had it disappears and there is no "Solicitar". */
  fallbackFocus: RefObject<HTMLElement | null>;
}

/**
 * State of the alerts of this device while the stop view is open (passenger_alert_ui design §1):
 * kept up to date by /ws/passenger (or GET /alerts/mine every 30 s while it is down), with the
 * create and cancel actions, the polite announcements of the events (AC-11) and the focus
 * when a control of an alert disappears (AC-05, AC-09, AC-11).
 */
export function AlertsProvider({ children, fallbackFocus }: AlertsProviderProps) {
  const { t } = useTranslation();
  const announce = useAnnounce();
  const [state, setState] = useState<AlertsState>(INITIAL_ALERTS_STATE);
  // Synchronous copy of the state: messages are applied one after another, each on the last.
  const current = useRef<AlertsState>(INITIAL_ALERTS_STATE);
  // Bumped by local changes: a GET /alerts/mine started before one of them is stale.
  const generation = useRef(0);
  const cancelling = useRef(new Set<string>());
  const requestButtons = useRef(new Map<string, HTMLButtonElement>());
  const statusBoxes = useRef(new Map<string, HTMLElement>());
  const pendingFocus = useRef<FocusTarget | null>(null);
  const [focusTick, setFocusTick] = useState(0);

  const apply = useCallback((action: PassengerMessage | LocalAction) => {
    const next = alertsReducer(current.current, action);
    current.current = next;
    setState(next);
  }, []);

  const requestFocus = useCallback((target: FocusTarget) => {
    pendingFocus.current = target;
    setFocusTick((tick) => tick + 1);
  }, []);

  // After painting, the control that must get the focus exists (or not: then the h2).
  useEffect(() => {
    const target = pendingFocus.current;
    if (target === null) return;
    pendingFocus.current = null;
    const element =
      target.target === 'cancel'
        ? statusBoxes.current.get(target.alertId)?.querySelector('button')
        : requestButtons.current.get(target.tripKey);
    (element ?? fallbackFocus.current)?.focus();
  }, [focusTick, fallbackFocus]);

  const handleMessage = useCallback(
    (message: PassengerMessage) => {
      const before = current.current;
      const active = document.activeElement;
      const focusLost = removedAlerts(before, message).find(
        (alert) => active !== null && statusBoxes.current.get(alert.alert_id)?.contains(active),
      );
      const announcement = eventAnnouncement(message, before, t);
      apply(message);
      if (focusLost !== undefined) requestFocus({ target: 'request', tripKey: tripKey(focusLost) });
      if (announcement !== null) announce(announcement, 'polite');
    },
    [apply, requestFocus, announce, t],
  );

  const { connected } = usePassengerSocket(handleMessage);
  const connectedNow = useRef(connected);
  useEffect(() => {
    connectedNow.current = connected;
  }, [connected]);

  // Fallback while the WebSocket is down: GET /alerts/mine every 30 s, as a snapshot. Not
  // while the browser is offline: the view waits for the connection before calling the API
  // (passenger_stop_view.AC-18), and the socket reconnects as soon as it is back.
  const online = useOnline();
  useEffect(() => {
    if (connected || !online) return;
    let active = true;
    const poll = async () => {
      const started = generation.current;
      try {
        const { data } = await apiSend<MyAlertsResponse>('GET', '/alerts/mine');
        if (!active || connectedNow.current || started !== generation.current) return;
        const message = toPassengerMessage({ type: 'alerts.snapshot', alerts: data?.alerts });
        if (message !== null) handleMessage(message);
      } catch {
        // Still without connection: the next round will try again.
      }
    };
    const interval = setInterval(() => void poll(), FALLBACK_POLL_MS);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [connected, online, handleMessage]);

  const create = useCallback(
    async (input: CreateAlertInput): Promise<CreateOutcome> => {
      let alert: Alert | null;
      try {
        alert = (await apiSend<Alert>('POST', '/alerts', input)).data;
      } catch (error) {
        return createError(error);
      }
      if (alert === null) return { error: 'network' };
      generation.current += 1;
      apply({ type: 'local.created', alert });
      announce(t('alert.requested', { line: alert.line }), 'polite');
      requestFocus({ target: 'cancel', alertId: alert.alert_id });
      return 'ok';
    },
    [apply, announce, requestFocus, t],
  );

  const cancel = useCallback(
    async (alertId: string): Promise<CancelOutcome> => {
      const alert = current.current.alerts[alertId];
      if (alert === undefined || cancelling.current.has(alertId)) return 'gone';
      cancelling.current.add(alertId);
      let outcome: CancelOutcome;
      try {
        await apiSend('DELETE', `/alerts/${encodeURIComponent(alertId)}`);
        outcome = 'ok';
      } catch (error) {
        outcome = error instanceof ApiError && error.status === 404 ? 'gone' : 'network';
      } finally {
        cancelling.current.delete(alertId);
      }
      if (outcome === 'network') {
        announce(t('alert.cancelFailed'), 'polite');
        return outcome;
      }
      generation.current += 1;
      apply({ type: 'local.removed', alert_id: alertId });
      announce(t(outcome === 'ok' ? 'alert.cancelled' : 'alert.alreadyGone'), 'polite');
      requestFocus({ target: 'request', tripKey: tripKey(alert) });
      return outcome;
    },
    [apply, announce, requestFocus, t],
  );

  const requestButtonRef = useCallback(
    (key: string) => (element: HTMLButtonElement | null) => {
      if (element === null) requestButtons.current.delete(key);
      else requestButtons.current.set(key, element);
    },
    [],
  );

  const statusRef = useCallback(
    (alertId: string) => (element: HTMLElement | null) => {
      if (element === null) statusBoxes.current.delete(alertId);
      else statusBoxes.current.set(alertId, element);
    },
    [],
  );

  const value = useMemo<AlertsContextValue>(() => {
    const all = Object.values(state.alerts);
    return {
      alertFor: (stopId, line) =>
        all.find((alert) => alert.stop_id === stopId && alert.line === line) ?? null,
      alertsAt: (stopId) => all.filter((alert) => alert.stop_id === stopId),
      create,
      cancel,
      connected,
      requestButtonRef,
      statusRef,
    };
  }, [state, create, cancel, connected, requestButtonRef, statusRef]);

  return <AlertsContext.Provider value={value}>{children}</AlertsContext.Provider>;
}

export function useAlerts(): AlertsContextValue {
  const value = useContext(AlertsContext);
  if (value === null) throw new Error('useAlerts() must be used inside <AlertsProvider>');
  return value;
}

/** The alerts context, or null outside the stop view (e.g. an ArrivalRow rendered alone). */
export function useOptionalAlerts(): AlertsContextValue | null {
  return useContext(AlertsContext);
}
