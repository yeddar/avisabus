import { act, render, screen } from '@testing-library/react';
import { Link, RouterProvider, createMemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it } from 'vitest';

import { usePageTitle } from '../usePageTitle';

function View({ title, next }: { title: string; next?: string }) {
  usePageTitle(title);
  return (
    <main>
      <h1>{title}</h1>
      {next !== undefined && <Link to={next}>go</Link>}
    </main>
  );
}

function renderRouter(initialEntries = ['/']) {
  const router = createMemoryRouter(
    [
      { path: '/', element: <View title="Home" next="/stop" /> },
      { path: '/stop', element: <View title="Stop 508" next="/" /> },
    ],
    { initialEntries },
  );
  render(<RouterProvider router={router} />);
  return router;
}

describe('usePageTitle', () => {
  afterEach(() => {
    document.title = '';
  });

  it('[frontend_i18n.AC-11] sets the document title as "<view title> · AvisaBus"', () => {
    renderRouter();

    expect(document.title).toBe('Home · AvisaBus');
  });

  it('[frontend_i18n.AC-11] does not move focus on the initial load', () => {
    renderRouter();

    expect(document.activeElement).toBe(document.body);
  });

  it('[frontend_i18n.AC-11] updates the title and focuses the new h1 after navigating', async () => {
    const router = renderRouter();

    await act(async () => {
      screen.getByRole('link', { name: 'go' }).click();
    });

    const heading = screen.getByRole('heading', { level: 1, name: 'Stop 508' });
    expect(document.title).toBe('Stop 508 · AvisaBus');
    expect(heading).toHaveAttribute('tabindex', '-1');
    expect(document.activeElement).toBe(heading);
    expect(router.state.location.pathname).toBe('/stop');
  });

  it('[frontend_i18n.AC-11] also focuses the h1 when navigating programmatically and back', async () => {
    const router = renderRouter();

    await act(async () => {
      await router.navigate('/stop');
    });
    await act(async () => {
      await router.navigate(-1);
    });

    expect(document.title).toBe('Home · AvisaBus');
    expect(document.activeElement).toBe(screen.getByRole('heading', { level: 1, name: 'Home' }));
  });

  it('[frontend_i18n.AC-11] updates the title when the view title changes (e.g. language)', () => {
    const router = createMemoryRouter([{ path: '/', element: <View title="Inicio" /> }]);
    const { rerender } = render(<RouterProvider router={router} />);
    expect(document.title).toBe('Inicio · AvisaBus');

    const router2 = createMemoryRouter([{ path: '/', element: <View title="Inici" /> }]);
    rerender(<RouterProvider router={router2} />);

    expect(document.title).toBe('Inici · AvisaBus');
    expect(document.activeElement).toBe(document.body);
  });
});
