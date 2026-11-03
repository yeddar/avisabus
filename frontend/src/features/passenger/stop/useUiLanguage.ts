import { useTranslation } from 'react-i18next';

import {
  DEFAULT_LANGUAGE,
  isLanguage,
  type Language,
  toHtmlLang,
} from '../../../shared/i18n/languages';

/** Current interface language, for the Intl-based formatters. */
export function useUiLanguage(): Language {
  const { i18n } = useTranslation();
  return isLanguage(i18n.language) ? i18n.language : DEFAULT_LANGUAGE;
}

/**
 * `lang` for GTFS/SAE names inside translated sentences (same rule as GtfsText,
 * frontend_i18n.AC-06): Valencian when the interface is in Spanish.
 */
export function gtfsLang(language: Language): string | undefined {
  return language === 'es' ? toHtmlLang('ca') : undefined;
}
