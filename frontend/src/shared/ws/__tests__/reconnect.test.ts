import { describe, expect, it } from 'vitest';

import { RECONNECT_STEPS_S, nextDelayMs } from '../reconnect';

describe('nextDelayMs', () => {
  it('[passenger_alert_ui.AC-10] waits 1, 2, 4, 8, 16 and then 30 s', () => {
    expect(RECONNECT_STEPS_S).toEqual([1, 2, 4, 8, 16, 30]);
    const centre = () => 0.5;

    expect([0, 1, 2, 3, 4, 5, 6, 50].map((attempt) => nextDelayMs(attempt, centre))).toEqual([
      1_000, 2_000, 4_000, 8_000, 16_000, 30_000, 30_000, 30_000,
    ]);
  });

  it('[passenger_alert_ui.AC-10] varies each wait randomly by ±20 %', () => {
    expect(nextDelayMs(0, () => 0)).toBe(800);
    expect(nextDelayMs(5, () => 0)).toBe(24_000);
    expect(nextDelayMs(0, () => 0.999_999)).toBeLessThanOrEqual(1_200);
    expect(nextDelayMs(0, () => 0.999_999)).toBeGreaterThan(1_199);
    expect(nextDelayMs(5, () => 0.25)).toBe(27_000);
  });

  it('[passenger_alert_ui.AC-10] uses Math.random by default and stays within the bounds', () => {
    for (let i = 0; i < 50; i += 1) {
      const delay = nextDelayMs(2);
      expect(delay).toBeGreaterThanOrEqual(3_200);
      expect(delay).toBeLessThanOrEqual(4_800);
    }
  });
});
