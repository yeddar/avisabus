import { render, type RenderOptions, type RenderResult } from '@testing-library/react';
import type { i18n as I18n } from 'i18next';
import type { ReactElement } from 'react';
import { I18nextProvider } from 'react-i18next';

import { initI18n } from '../shared/i18n/i18n';
import type { Language } from '../shared/i18n/languages';

export interface ProvidersOptions extends Omit<RenderOptions, 'wrapper'> {
  language?: Language;
}

/** Renders `ui` with i18n initialised in the requested language (Spanish by default). */
export function renderWithProviders(
  ui: ReactElement,
  { language = 'es', ...options }: ProvidersOptions = {},
): RenderResult & { i18n: I18n } {
  const i18n = initI18n({ language });
  const result = render(ui, {
    wrapper: ({ children }) => <I18nextProvider i18n={i18n}>{children}</I18nextProvider>,
    ...options,
  });
  return { ...result, i18n };
}
