import type { QueryClient } from '@tanstack/react-query';
import { QueryClientProvider } from '@tanstack/react-query';
import { render, type RenderOptions, type RenderResult } from '@testing-library/react';
import type { i18n as I18n } from 'i18next';
import type { ReactElement } from 'react';
import { I18nextProvider } from 'react-i18next';

import { createQueryClient } from '../shared/api/queryClient';
import { initI18n } from '../shared/i18n/i18n';
import type { Language } from '../shared/i18n/languages';
import { AnnouncerProvider } from '../shared/ui/Announcer';

export interface ProvidersOptions extends Omit<RenderOptions, 'wrapper'> {
  language?: Language;
  /** Defaults to a new client per render, so cached data never leaks between tests. */
  queryClient?: QueryClient;
}

/**
 * Renders `ui` with i18n initialised in the requested language (Spanish by default), a
 * TanStack Query client and the announcement regions mounted.
 */
export function renderWithProviders(
  ui: ReactElement,
  { language = 'es', queryClient = createQueryClient(), ...options }: ProvidersOptions = {},
): RenderResult & { i18n: I18n; queryClient: QueryClient } {
  const i18n = initI18n({ language });
  const result = render(ui, {
    wrapper: ({ children }) => (
      <QueryClientProvider client={queryClient}>
        <I18nextProvider i18n={i18n}>
          <AnnouncerProvider>{children}</AnnouncerProvider>
        </I18nextProvider>
      </QueryClientProvider>
    ),
    ...options,
  });
  return { ...result, i18n, queryClient };
}
