import type { Language } from './languages';
import { translations } from './resources';

const TIME_ZONE = 'Europe/Madrid';
const METERS_PER_KILOMETER = 1000;

function interpolate(template: string, values: Record<string, string>): string {
  return template.replace(/\{\{(\w+)\}\}/g, (match, name: string) => values[name] ?? match);
}

function integer(value: number, lang: Language): string {
  return new Intl.NumberFormat(lang, { maximumFractionDigits: 0 }).format(value);
}

/** "5 min" for display and "5 minutos" / "5 minuts" for accessible text. */
export function formatMinutes(minutes: number, lang: Language): { short: string; long: string } {
  const time = translations[lang].time;
  const count = integer(minutes, lang);
  const plural = new Intl.PluralRules(lang).select(minutes) === 'one' ? 'one' : 'other';
  const long = plural === 'one' ? time.minutes_one : time.minutes_other;
  return {
    short: interpolate(time.minutesShort, { count }),
    long: interpolate(long, { count }),
  };
}

/** 24-hour clock time in Europe/Madrid, e.g. "22:41". */
export function formatClockTime(iso: string, lang: Language): string {
  return new Intl.DateTimeFormat(lang, {
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
    timeZone: TIME_ZONE,
  }).format(new Date(iso));
}

/** Metres below 1 km ("850 m"); kilometres with one decimal from 1 km ("1,2 km"). */
export function formatDistance(meters: number, lang: Language): string {
  const distance = translations[lang].distance;
  const rounded = Math.round(meters);
  if (rounded < METERS_PER_KILOMETER) {
    return interpolate(distance.meters, { value: integer(rounded, lang) });
  }
  const kilometers = new Intl.NumberFormat(lang, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(rounded / METERS_PER_KILOMETER);
  return interpolate(distance.kilometers, { value: kilometers });
}
