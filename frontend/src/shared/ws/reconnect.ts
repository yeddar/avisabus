/** Waits between reconnection attempts of the passenger WebSocket (passenger_alert_ui.AC-10). */
export const RECONNECT_STEPS_S = [1, 2, 4, 8, 16, 30];

const JITTER = 0.2;

/**
 * Wait before reconnection attempt `attempt` (0 for the first one after a close): 1, 2, 4, 8,
 * 16 and then always 30 s, each varied randomly by ±20 % so that every passenger does not
 * reconnect at the same moment after a server restart.
 */
export function nextDelayMs(attempt: number, random: () => number = Math.random): number {
  const index = Math.min(Math.max(attempt, 0), RECONNECT_STEPS_S.length - 1);
  const base = (RECONNECT_STEPS_S[index] ?? 30) * 1000;
  return Math.round(base * (1 - JITTER + 2 * JITTER * random()));
}
