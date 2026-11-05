import { useEffect, useLayoutEffect, useRef, useState } from 'react';

import {
  type PassengerMessage,
  parsePassengerMessage,
} from '../../features/passenger/alerts/alertsReducer';
import { getDeviceId } from '../device/deviceId';
import { useOnline } from '../hooks/useOnline';
import { nextDelayMs } from './reconnect';

/** WebSocket of the passenger on the same origin as the page (realtime_events design §3). */
export function passengerSocketUrl(
  location: Pick<Location, 'protocol' | 'host'> = window.location,
): string {
  return `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws/passenger`;
}

/**
 * Keeps /ws/passenger open while mounted (passenger_alert_ui.AC-10): sends the `hello` with the
 * device identifier (only in that message, never in the URL), answers `ping` with `pong` and
 * passes every other valid message to `onMessage`. After any close, whatever its code (1001,
 * 1012, 4429…, realtime_events v1.1), it reconnects after 1, 2, 4, 8, 16, 30 s (±20 %), never
 * while the browser is offline; the waits start again after each snapshot. `connected` is true
 * from the snapshot until the close.
 */
export function usePassengerSocket(onMessage: (message: PassengerMessage) => void): {
  connected: boolean;
} {
  const online = useOnline();
  const [connected, setConnected] = useState(false);
  const handler = useRef(onMessage);
  useLayoutEffect(() => {
    handler.current = onMessage;
  });

  useEffect(() => {
    if (!online) return;
    let socket: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let attempt = 0;

    function connect() {
      const ws = new WebSocket(passengerSocketUrl());
      socket = ws;
      ws.onopen = () => ws.send(JSON.stringify({ type: 'hello', device_id: getDeviceId() }));
      ws.onmessage = (event: MessageEvent) => {
        const message = parsePassengerMessage(event.data);
        if (message === null) return;
        if (message.type === 'ping') {
          ws.send(JSON.stringify({ type: 'pong' }));
          return;
        }
        if (message.type === 'alerts.snapshot') {
          attempt = 0;
          setConnected(true);
        }
        handler.current(message);
      };
      ws.onclose = () => {
        socket = null;
        setConnected(false);
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
      setConnected(false);
    };
  }, [online]);

  return { connected };
}
