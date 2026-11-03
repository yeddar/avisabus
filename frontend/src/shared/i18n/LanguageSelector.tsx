import { useId, type ChangeEvent } from 'react';
import { useTranslation } from 'react-i18next';

import {
  DEFAULT_LANGUAGE,
  SUPPORTED_LANGUAGES,
  SUPPORTED_LANGUAGE_NAMES,
  isLanguage,
  toHtmlLang,
} from './languages';

/** Native select with a small visible label; each language is named in itself (CU-06). */
export function LanguageSelector() {
  const { t, i18n } = useTranslation();
  const id = useId();
  const current = isLanguage(i18n.language) ? i18n.language : DEFAULT_LANGUAGE;

  function changeLanguage(event: ChangeEvent<HTMLSelectElement>) {
    const next = event.target.value;
    if (isLanguage(next)) {
      void i18n.changeLanguage(next);
    }
  }

  return (
    <div className="flex items-center gap-2">
      <label htmlFor={id} className="text-sm text-text-muted">
        {t('language.label')}
      </label>
      <select
        id={id}
        value={current}
        onChange={changeLanguage}
        className="min-h-11 rounded-lg border border-control-border bg-surface px-3 text-base text-text"
      >
        {SUPPORTED_LANGUAGES.map((language) => (
          <option key={language} value={language} lang={toHtmlLang(language)}>
            {SUPPORTED_LANGUAGE_NAMES[language]}
          </option>
        ))}
      </select>
    </div>
  );
}
