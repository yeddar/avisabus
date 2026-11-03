import { screen } from '@testing-library/react';
import { RouterProvider, createMemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it } from 'vitest';

import { setLastStop } from '../../features/passenger/stop/lastStop';
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

describe('HomePage last stop', () => {
  afterEach(() => {
    localStorage.clear();
    document.title = '';
  });

  it.each([
    ['es', "Tu última parada: Parc de l'Oest - Enguera"],
    ['ca', "La teua última parada: Parc de l'Oest - Enguera"],
  ] as const)(
    '[passenger_stop_view.AC-19] offers a link to the last stop opened on the device (%s)',
    (language, name) => {
      setLastStop({
        stopId: '508',
        name: "Parc de l'Oest - Enguera",
        token: 'AbCdEfGhIjKlMnOpQrStUv',
      });

      renderHome(language);

      const link = screen.getByRole('link', { name });
      expect(link).toHaveAttribute('href', '/p/508?t=AbCdEfGhIjKlMnOpQrStUv');
      const name_ = screen.getByText("Parc de l'Oest - Enguera");
      if (language === 'es') expect(name_).toHaveAttribute('lang', 'ca-ES-valencia');
      else expect(name_).not.toHaveAttribute('lang');
    },
  );

  it('[passenger_stop_view.AC-19] shows no link when no stop has been opened', () => {
    renderHome('es');

    expect(screen.queryByRole('link', { name: /última parada/ })).toBeNull();
  });

  it('[passenger_stop_view.AC-19] encodes the stop id and token in the link', () => {
    setLastStop({ stopId: 'a/b', name: 'X', token: 'to+k/en' });

    renderHome('es');

    expect(screen.getByRole('link', { name: 'Tu última parada: X' })).toHaveAttribute(
      'href',
      '/p/a%2Fb?t=to%2Bk%2Fen',
    );
  });
});
