import type { Language } from '../../../shared/i18n/languages';

const TIME_ZONE = 'Europe/Madrid';

/** "08:40:12": time of the data in València, with seconds (passenger_stop_view.AC-14). */
export function formatUpdateTime(iso: string, lang: Language): string {
  return new Intl.DateTimeFormat(lang, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hourCycle: 'h23',
    timeZone: TIME_ZONE,
  }).format(new Date(iso));
}
