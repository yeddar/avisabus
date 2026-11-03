import ca from '../../locales/ca-valencia/translation.json';
import es from '../../locales/es/translation.json';
import type { Language } from './languages';

export type Translation = typeof es;

/** Bundled translations. Valencian lives in locales/ca-valencia/ and is registered as `ca`. */
export const translations: Record<Language, Translation> = { es, ca };

export const resources = {
  es: { translation: es },
  ca: { translation: ca },
} as const;
