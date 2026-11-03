import { useCallback, useLayoutEffect, useState, useSyncExternalStore } from 'react';

export const SERVER_CLOCK_TICK_MS = 15_000;

/**
 * Device clock corrected with the server time. The offset is taken when a new `generated_at`
 * is seen (i.e. when a response arrives): offset = generated_at − device now.
 */
class ServerClock {
  private offset = 0;
  private generatedAt: string | undefined = undefined;
  private snapshot = new Date();
  private listeners = new Set<() => void>();

  getSnapshot = (): Date => this.snapshot;

  sync(generatedAt: string | undefined): void {
    if (generatedAt === this.generatedAt) return;
    this.generatedAt = generatedAt;
    const parsed = generatedAt === undefined ? Number.NaN : Date.parse(generatedAt);
    this.offset = Number.isNaN(parsed) ? 0 : parsed - Date.now();
    this.tick();
  }

  subscribe(onChange: () => void, tickMs: number): () => void {
    this.listeners.add(onChange);
    const interval = setInterval(() => this.tick(), tickMs);
    return () => {
      clearInterval(interval);
      this.listeners.delete(onChange);
    };
  }

  private tick(): void {
    this.snapshot = new Date(Date.now() + this.offset);
    this.listeners.forEach((listener) => listener());
  }
}

/**
 * Current server time, re-rendering every `tickMs` (passenger_stop_view.AC-13). Without a
 * response yet, the device time.
 */
export function useServerNow(generatedAt: string | undefined, tickMs = SERVER_CLOCK_TICK_MS): Date {
  const [clock] = useState(() => new ServerClock());
  const subscribe = useCallback(
    (onChange: () => void) => clock.subscribe(onChange, tickMs),
    [clock, tickMs],
  );

  useLayoutEffect(() => {
    clock.sync(generatedAt);
  }, [clock, generatedAt]);

  return useSyncExternalStore(subscribe, clock.getSnapshot, clock.getSnapshot);
}
