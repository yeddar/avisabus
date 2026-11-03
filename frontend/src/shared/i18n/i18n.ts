import { createInstance, type i18n as I18n, type PostProcessorModule } from 'i18next';
import { initReactI18next } from 'react-i18next';

import ca from '../../locales/ca-valencia/translation.json';
import es from '../../locales/es/translation.json';
import { safeStorage } from '../device/storage';
import { detectInitialLanguage } from './detectLanguage';
import {
  DEFAULT_LANGUAGE,
  LANGUAGE_STORAGE_KEY,
  isLanguage,
  type Language,
  toHtmlLang,
} from './languages';

/** Valencian resources live in locales/ca-valencia/ and are registered under the `ca` code. */
const resources = {
  es: { translation: es },
  ca: { translation: ca },
} as const;

const FALLBACK_WARNING = 'devFallbackWarning';

/**
 * i18next does not report a key as missing when the fallback language (Spanish) has it, so in
 * development this post-processor warns whenever a text was resolved in a language other than
 * the active one (frontend_i18n.AC-05).
 */
const fallbackWarning: PostProcessorModule = {
  type: 'postProcessor',
  name: FALLBACK_WARNING,
  process(value, key, options, translator: { language?: string }) {
    const resolved = (options as { i18nResolved?: { usedLng?: string; res?: unknown } })
      .i18nResolved;
    const active = translator.language;
    if (
      resolved?.res !== undefined &&
      resolved.usedLng !== undefined &&
      resolved.usedLng !== active
    ) {
      console.warn(
        `[i18n] Missing key "${String(key)}" in "${String(active)}"; using "${resolved.usedLng}".`,
      );
    }
    return value;
  },
};

function browserLanguages(): readonly string[] {
  return typeof navigator === 'undefined' ? [] : navigator.languages;
}

function applyDocumentLang(lang: Language): void {
  document.documentElement.lang = toHtmlLang(lang);
}

/**
 * Creates and initialises the i18next instance synchronously (bundled resources) and makes it
 * the instance used by react-i18next. Initial language: `options.language` or, if absent,
 * stored choice → browser → Spanish.
 */
export function initI18n(options: { language?: Language } = {}): I18n {
  const dev = import.meta.env.DEV;
  const language =
    options.language ??
    detectInitialLanguage(safeStorage.get(LANGUAGE_STORAGE_KEY), browserLanguages());

  const instance = createInstance();
  instance.use(initReactI18next);
  if (dev) {
    instance.use(fallbackWarning);
  }
  void instance.init({
    lng: language,
    fallbackLng: DEFAULT_LANGUAGE,
    supportedLngs: ['es', 'ca'],
    resources,
    initAsync: false,
    interpolation: { escapeValue: false },
    returnNull: false,
    saveMissing: dev,
    missingKeyHandler: dev
      ? (_lngs, _ns, key) => {
          console.warn(`[i18n] Missing key "${key}" in every language.`);
        }
      : false,
    postProcess: dev ? [FALLBACK_WARNING] : false,
    postProcessPassResolved: dev,
  });

  applyDocumentLang(language);
  // Subscribed after init: only later changes (the person's choice) are remembered.
  instance.on('languageChanged', (lng: string) => {
    if (isLanguage(lng)) {
      safeStorage.set(LANGUAGE_STORAGE_KEY, lng);
      applyDocumentLang(lng);
    }
  });

  return instance;
}
