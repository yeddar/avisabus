import { describe, expect, it } from 'vitest';

import { formatClockTime, formatDistance, formatMinutes } from '../format';

describe('formatMinutes', () => {
  it.each([
    [1, 'es', '1 min', '1 minuto'],
    [5, 'es', '5 min', '5 minutos'],
    [0, 'es', '0 min', '0 minutos'],
    [1, 'ca', '1 min', '1 minut'],
    [5, 'ca', '5 min', '5 minuts'],
    [12, 'ca', '12 min', '12 minuts'],
  ] as const)(
    '[frontend_i18n.AC-09] %i minute(s) in %s → short "%s", accessible "%s"',
    (minutes, lang, short, long) => {
      expect(formatMinutes(minutes, lang)).toEqual({ short, long });
    },
  );
});

describe('formatClockTime', () => {
  it.each([
    // Winter (CET, UTC+1)
    ['2026-11-03T21:41:00Z', 'es', '22:41'],
    ['2026-11-03T21:41:00Z', 'ca', '22:41'],
    // Summer (CEST, UTC+2) and 24-hour midnight
    ['2026-07-01T22:05:00Z', 'es', '00:05'],
    ['2026-07-01T07:09:30Z', 'ca', '09:09'],
    // Offsets in the input are honoured
    ['2026-11-03T22:41:00+01:00', 'es', '22:41'],
  ] as const)(
    '[frontend_i18n.AC-09] %s in %s is shown as %s (24 h, Europe/Madrid)',
    (iso, lang, expected) => {
      expect(formatClockTime(iso, lang)).toBe(expected);
    },
  );
});

describe('formatDistance', () => {
  it.each([
    [0, 'es', '0 m'],
    [850, 'es', '850 m'],
    [849.6, 'ca', '850 m'],
    [999.4, 'es', '999 m'],
    [999.6, 'es', '1,0 km'],
    [1000, 'es', '1,0 km'],
    [1234, 'es', '1,2 km'],
    [1250, 'ca', '1,3 km'],
    [12345, 'ca', '12,3 km'],
  ] as const)('[frontend_i18n.AC-09] %d metres in %s → %s', (meters, lang, expected) => {
    expect(formatDistance(meters, lang)).toBe(expected);
  });
});
