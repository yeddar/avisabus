import { act, fireEvent, screen } from '@testing-library/react';
import { RouterProvider, createMemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it } from 'vitest';

import type { Language } from '../../shared/i18n/languages';
import { renderWithProviders } from '../../test/render';
import { routes } from '../routes';

function renderAt(path: string, language: Language = 'es') {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  renderWithProviders(<RouterProvider router={router} />, { language });
  return router;
}

describe('NotFoundPage', () => {
  afterEach(() => {
    document.title = '';
  });

  it.each([
    ['/no-existe', 'es', 'Página no encontrada', 'Ir a la portada'],
    ['/p', 'es', 'Página no encontrada', 'Ir a la portada'],
    ['/p/508/otra', 'ca', 'Pàgina no trobada', 'Ves a la portada'],
  ] as const)(
    '[passenger_stop_view.AC-20] %s in %s shows "%s" with a link to the home page',
    (path, language, title, home) => {
      renderAt(path, language);

      expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(title);
      expect(screen.getByRole('main')).toContainElement(screen.getByRole('heading', { level: 1 }));
      expect(screen.getByRole('link', { name: home })).toHaveAttribute('href', '/');
      expect(document.title).toBe(`${title} · AvisaBus`);
    },
  );

  it('[passenger_stop_view.AC-20] the link opens the home page', async () => {
    const router = renderAt('/no-existe');

    await act(async () => {
      fireEvent.click(screen.getByRole('link', { name: 'Ir a la portada' }));
    });

    expect(router.state.location.pathname).toBe('/');
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('AvisaBus');
  });
});
