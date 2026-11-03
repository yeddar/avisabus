/** Interface languages. Internal codes are `es` and `ca` (i18next and Intl.PluralRules use `ca`). */
export type Language = 'es' | 'ca';

export const SUPPORTED_LANGUAGES: readonly Language[] = ['es', 'ca'];

export const DEFAULT_LANGUAGE: Language = 'es';

export const LANGUAGE_STORAGE_KEY = 'avisabus.language';

/**
 * Each language is named in itself, so these names are never translated. They are the only
 * allowed exception to the no-literal-string rule (frontend_i18n design §3).
 */
export const SUPPORTED_LANGUAGE_NAMES: Record<Language, string> = {
  es: 'Castellano',
  ca: 'Valencià',
};

export function isLanguage(value: unknown): value is Language {
  return typeof value === 'string' && (SUPPORTED_LANGUAGES as readonly string[]).includes(value);
}

/** Value for the HTML `lang` attribute. */
export function toHtmlLang(lang: Language): 'es' | 'ca-ES-valencia' {
  return lang === 'ca' ? 'ca-ES-valencia' : 'es';
}
