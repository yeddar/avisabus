import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { initI18n } from '../i18n';
import { LANGUAGE_STORAGE_KEY } from '../languages';

function stubNavigatorLanguages(languages: readonly string[]) {
  vi.spyOn(window.navigator, 'languages', 'get').mockReturnValue(languages);
}

describe('initI18n', () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.lang = '';
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllEnvs();
    localStorage.clear();
  });

  it('[frontend_i18n.AC-03] sets lang="es" on the document for Spanish', () => {
    initI18n({ language: 'es' });

    expect(document.documentElement.lang).toBe('es');
  });

  it('[frontend_i18n.AC-03] sets lang="ca-ES-valencia" on the document for Valencian', () => {
    initI18n({ language: 'ca' });

    expect(document.documentElement.lang).toBe('ca-ES-valencia');
  });

  it('[frontend_i18n.AC-03] updates the document lang when the language changes', async () => {
    const i18n = initI18n({ language: 'es' });

    await i18n.changeLanguage('ca');
    expect(document.documentElement.lang).toBe('ca-ES-valencia');

    await i18n.changeLanguage('es');
    expect(document.documentElement.lang).toBe('es');
  });

  it('[frontend_i18n.AC-02] remembers a language change on the device', async () => {
    const i18n = initI18n({ language: 'es' });

    await i18n.changeLanguage('ca');

    expect(localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe('ca');
  });

  it('[frontend_i18n.AC-02] does not store the detected language when nobody chose it', () => {
    stubNavigatorLanguages(['ca-ES']);

    const i18n = initI18n();

    expect(i18n.language).toBe('ca');
    expect(localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBeNull();
  });

  it('[frontend_i18n.AC-01] starts in Valencian when the first browser language is ca-*', () => {
    stubNavigatorLanguages(['ca-ES-valencia', 'es']);

    const i18n = initI18n();

    expect(i18n.language).toBe('ca');
    expect(i18n.t('language.label')).toBe('Llengua');
  });

  it('[frontend_i18n.AC-02] a stored choice prevails over the browser language', () => {
    stubNavigatorLanguages(['ca-ES']);
    localStorage.setItem(LANGUAGE_STORAGE_KEY, 'es');

    const i18n = initI18n();

    expect(i18n.language).toBe('es');
    expect(i18n.t('language.label')).toBe('Idioma');
  });

  it('[frontend_i18n.AC-05] shows the Spanish text when a key is missing in Valencian', () => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const i18n = initI18n({ language: 'ca' });
    i18n.addResource('es', 'translation', 'test.onlyInSpanish', 'Solo en castellano');

    expect(i18n.t('test.onlyInSpanish')).toBe('Solo en castellano');
  });

  it('[frontend_i18n.AC-05] warns in the console in development when falling back to Spanish', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const i18n = initI18n({ language: 'ca' });
    i18n.addResource('es', 'translation', 'test.onlyInSpanish', 'Solo en castellano');

    i18n.t('test.onlyInSpanish');

    expect(warn).toHaveBeenCalledTimes(1);
    expect(String(warn.mock.calls[0]?.join(' '))).toContain('test.onlyInSpanish');
  });

  it('[frontend_i18n.AC-05] warns in development when a key is missing in every language', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const i18n = initI18n({ language: 'es' });

    i18n.t('test.missingEverywhere');

    expect(warn).toHaveBeenCalled();
    expect(String(warn.mock.calls[0]?.join(' '))).toContain('test.missingEverywhere');
  });

  it('[frontend_i18n.AC-05] does not warn for keys present in the active language', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const i18n = initI18n({ language: 'ca' });

    expect(i18n.t('layout.skipToContent')).toBe('Botar al contingut');
    expect(i18n.t('time.minutes', { count: 5 })).toBe('5 minuts');
    expect(warn).not.toHaveBeenCalled();
  });

  it('[frontend_i18n.AC-05] does not warn outside development', () => {
    vi.stubEnv('DEV', false);
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const i18n = initI18n({ language: 'ca' });
    i18n.addResource('es', 'translation', 'test.onlyInSpanish', 'Solo en castellano');

    expect(i18n.t('test.onlyInSpanish')).toBe('Solo en castellano');
    i18n.t('test.missingEverywhere');
    expect(warn).not.toHaveBeenCalled();
  });
});
