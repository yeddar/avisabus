import { describe, expect, it } from 'vitest';

import { detectInitialLanguage } from '../detectLanguage';
import { LANGUAGE_STORAGE_KEY, SUPPORTED_LANGUAGES, toHtmlLang } from '../languages';

describe('detectInitialLanguage', () => {
  it.each([
    [['ca'], 'ca'],
    [['ca-ES'], 'ca'],
    [['ca-ES-valencia', 'es'], 'ca'],
    [['CA-es'], 'ca'],
    [['es-ES', 'ca'], 'es'],
    [['en-GB', 'ca-ES'], 'es'],
    [['es'], 'es'],
    [['fr-FR'], 'es'],
    [[], 'es'],
  ] as const)(
    '[frontend_i18n.AC-01] navigator languages %j without stored choice give %s',
    (navigatorLanguages, expected) => {
      expect(detectInitialLanguage(null, navigatorLanguages)).toBe(expected);
    },
  );

  it('[frontend_i18n.AC-01] does not treat languages that merely contain "ca" as Valencian', () => {
    expect(detectInitialLanguage(null, ['de-CA'])).toBe('es');
  });

  it.each([
    ['ca', ['es-ES'], 'ca'],
    ['es', ['ca-ES-valencia'], 'es'],
  ] as const)(
    '[frontend_i18n.AC-01] a valid stored choice %s wins over navigator %j',
    (stored, navigatorLanguages, expected) => {
      expect(detectInitialLanguage(stored, navigatorLanguages)).toBe(expected);
    },
  );

  it.each(['', 'en', 'ca-valencia', 'ES', 'null'])(
    '[frontend_i18n.AC-01] ignores an invalid stored value %j and falls back to the navigator',
    (stored) => {
      expect(detectInitialLanguage(stored, ['ca-ES'])).toBe('ca');
      expect(detectInitialLanguage(stored, ['es-ES'])).toBe('es');
    },
  );
});

describe('languages', () => {
  it('declares the supported languages and storage key', () => {
    expect(SUPPORTED_LANGUAGES).toEqual(['es', 'ca']);
    expect(LANGUAGE_STORAGE_KEY).toBe('avisabus.language');
  });

  it('[frontend_i18n.AC-03] maps internal codes to document lang values', () => {
    expect(toHtmlLang('es')).toBe('es');
    expect(toHtmlLang('ca')).toBe('ca-ES-valencia');
  });
});
