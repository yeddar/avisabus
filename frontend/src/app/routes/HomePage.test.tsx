import { screen } from '@testing-library/react';
import { RouterProvider, createMemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it } from 'vitest';

import type { Language } from '../../shared/i18n/languages';
import { renderWithProviders } from '../../test/render';
import { routes } from '../routes';

function renderHome(language: Language) {
  const router = createMemoryRouter(routes, { initialEntries: ['/'] });
  return renderWithProviders(<RouterProvider router={router} />, { language });
}

describe('HomePage', () => {
  afterEach(() => {
    localStorage.clear();
    document.title = '';
  });

  it.each([
    [
      'es',
      'Escanea el código QR de tu parada para ver cuándo llega tu autobús y solicitar parada al conductor.',
      'Inicio · AvisaBus',
    ],
    [
      'ca',
      'Escaneja el codi QR de la teua parada per a vore quan arriba el teu autobús i sol·licitar parada al conductor.',
      'Inici · AvisaBus',
    ],
  ] as const)(
    '[frontend_i18n.AC-15] shows the app title and the QR explanation in %s',
    (language, scanQr, title) => {
      renderHome(language);

      const main = screen.getByRole('main');
      const headings = screen.getAllByRole('heading', { level: 1 });
      expect(headings).toHaveLength(1);
      expect(headings[0]).toHaveTextContent('AvisaBus');
      expect(main).toContainElement(headings[0] ?? null);
      expect(screen.getByText(scanQr)).toBeInTheDocument();
      expect(main).toContainElement(screen.getByText(scanQr));
      expect(document.title).toBe(title);
    },
  );

  it('[frontend_i18n.AC-15] switches language in place', async () => {
    const { i18n } = renderHome('es');

    await i18n.changeLanguage('ca');

    expect(await screen.findByText(/Escaneja el codi QR/)).toBeInTheDocument();
    expect(document.title).toBe('Inici · AvisaBus');
  });
});
