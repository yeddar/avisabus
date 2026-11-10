import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';

import { useOnline } from '../../shared/hooks/useOnline';
import { nextDelayMs } from '../../shared/ws/reconnect';
import { DriverAuthError, driverApi, getDriverToken, loseDriverAuth } from './session';
import type { DriverView } from './types';

const POLL_INTERVAL_MS = 10_000;
const OK = 200;
/** Close code of /ws/driver for a token that is not of an open shift (driver_demand design §3). */
const INVALID_TOKEN = 4401;
const CLOSE_REASONS = ['ENDED', 'IDLE', 'REVOKED', 'REPLACED'] as const;

export type SessionCloseReason = (typeof CLOSE_REASONS)[number];
export type DriverSocketStatus = 'connecting' | 'connected' | 'disconnected';

type DriverMessage =
  | { type: 'ping' }
  | { type: 'session.closed'; reason: SessionCloseReason }
  | { type: 'driver.view'; view: DriverView };

/** WebSocket of the driver on the same origin as the page (driver_demand design §3). */
export function driverSocketUrl(
  location: Pick<Location, 'protocol' | 'host'> = window.location,
): string {
  return `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/driver`;
}

function parseMessage(raw: unknown): DriverMessage | null {
  if (typeof raw !== 'string') return null;
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return null;
  }
  if (typeof data !== 'object' || data === null || !('type' in data)) return null;
  if (data.type === 'ping') return { type: 'ping' };
  if (data.type === 'session.closed') {
    const reason = 'reason' in data ? data.reason : null;
    return {
      type: 'session.closed',
      reason: CLOSE_REASONS.includes(reason as SessionCloseReason)
        ? (reason as SessionCloseReason)
        : 'ENDED',
    };
  }
  if (data.type === 'driver.view' && 'stops' in data && Array.isArray(data.stops)) {
    return { type: 'driver.view', view: data as unknown as DriverView };
  }
  return null;
}

export interface DriverSocketOptions {
  /** A view from the socket or the polling; `initial`: first one after entering or reconnecting. */
  onView: (view: DriverView, meta: { initial: boolean }) => void;
  onClosed: (reason: SessionCloseReason) => void;
}

/**
 * Keeps /ws/driver open while mounted (driver_ui.AC-09, as passenger_alert_ui.AC-10): sends the
 * `hello` with the token (only in that message), answers `ping`, and reconnects after 1, 2, 4,
 * 8, 16, 30 s (±20 %), never while the browser is offline. While it is not connected it asks for
 * GET …/view every 10 s. `status` is `connected` from the first view until the close; `connecting`
 * only before the first close, so the view does not show "Sin conexión" while starting.
 */
export function useDriverSocket(options: DriverSocketOptions): { status: DriverSocketStatus } {
  const online = useOnline();
  const [socketStatus, setSocketStatus] = useState<DriverSocketStatus>('connecting');
  const handlers = useRef(options);
  useLayoutEffect(() => {
    handlers.current = options;
  });
  const awaitingFirstView = useRef(true);
  const lastGeneratedAt = useRef(Number.NEGATIVE_INFINITY);
  const closed = useRef(false);

  const deliver = useCallback((view: DriverView) => {
    const generatedAt = Date.parse(view.generated_at);
    if (generatedAt < lastGeneratedAt.current) return;
    lastGeneratedAt.current = generatedAt;
    const initial = awaitingFirstView.current;
    awaitingFirstView.current = false;
    handlers.current.onView(view, { initial });
  }, []);

  useEffect(() => {
    if (!online) return;
    let socket: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let attempt = 0;

    function connect() {
      const ws = new WebSocket(driverSocketUrl());
      socket = ws;
      ws.onopen = () => {
        awaitingFirstView.current = true;
        ws.send(JSON.stringify({ type: 'hello', session_token: getDriverToken() }));
      };
      ws.onmessage = (event: MessageEvent) => {
        const message = parseMessage(event.data);
        if (message === null) return;
        if (message.type === 'ping') {
          ws.send(JSON.stringify({ type: 'pong' }));
        } else if (message.type === 'session.closed') {
          closed.current = true;
          handlers.current.onClosed(message.reason);
        } else {
          attempt = 0;
          setSocketStatus('connected');
          deliver(message.view);
        }
      };
      ws.onclose = (event: CloseEvent) => {
        socket = null;
        if (closed.current) return;
        if (event.code === INVALID_TOKEN) {
          closed.current = true;
          loseDriverAuth();
          return;
        }
        setSocketStatus('disconnected');
        timer = setTimeout(connect, nextDelayMs(attempt));
        attempt += 1;
      };
    }

    connect();
    return () => {
      clearTimeout(timer);
      if (socket !== null) {
        socket.onopen = null;
        socket.onmessage = null;
        socket.onclose = null;
        socket.close(1000);
      }
    };
  }, [online, deliver]);

  const status: DriverSocketStatus = online ? socketStatus : 'disconnected';

  useEffect(() => {
    if (status === 'connected') return;
    const timer = setInterval(() => {
      if (closed.current) return;
      void driverApi<DriverView>('GET', '/driver/sessions/current/view')
        .then((result) => {
          if (result.status === OK && result.data !== null) deliver(result.data);
        })
        .catch((failure: unknown) => {
          // A 401 is reported through loseDriverAuth; anything else waits for the next tick.
          if (failure instanceof DriverAuthError) closed.current = true;
        });
    }, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [status, deliver]);

  return { status };
}
