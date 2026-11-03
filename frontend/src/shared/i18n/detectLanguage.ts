import { DEFAULT_LANGUAGE, isLanguage, type Language } from './languages';

/**
 * Initial interface language: a valid stored choice wins; otherwise Valencian when the FIRST
 * preferred browser language starts with `ca` (case-insensitive); otherwise Spanish.
 */
export function detectInitialLanguage(
  stored: string | null,
  navigatorLanguages: readonly string[],
): Language {
  if (isLanguage(stored)) {
    return stored;
  }
  const first = navigatorLanguages[0]?.toLowerCase() ?? '';
  if (first === 'ca' || first.startsWith('ca-')) {
    return 'ca';
  }
  return DEFAULT_LANGUAGE;
}
