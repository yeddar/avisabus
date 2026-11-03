import { act, screen, within } from '@testing-library/react';
import { RouterProvider, createMemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it } from 'vitest';

import type { Language } from '../shared/i18n/languages';
import { useAnnounce } from '../shared/ui/Announcer';
import { renderWithProviders } from '../test/render';
import { Layout } from './Layout';

const FOCUSABLE = 'a[href], button, select, input, textarea, [tabindex]:not([tabindex="-1"])';

function View() {
  useAnnounce(); // views can announce without creating regions
  return <h1>View title</h1>;
}

function renderLayout(language: Language = 'es') {
  const router = createMemoryRouter([
    { element: <Layout />, children: [{ path: '/', element: <View /> }] },
  ]);
  return renderWithProviders(<RouterProvider router={router} />, { language });
}

describe('Layout', () => {
  afterEach(() => localStorage.clear());

  it('[frontend_i18n.AC-10] has banner, main and contentinfo landmarks and a single h1', () => {
    renderLayout();

    expect(screen.getAllByRole('banner')).toHaveLength(1);
    expect(screen.getAllByRole('main')).toHaveLength(1);
    expect(screen.getAllByRole('contentinfo')).toHaveLength(1);
    const headings = screen.getAllByRole('heading', { level: 1 });
    expect(headings).toHaveLength(1);
    expect(screen.getByRole('main')).toContainElement(headings[0] ?? null);
  });

  it('[frontend_i18n.AC-10] the first focusable element is the skip link, which focuses main', () => {
    renderLayout();

    const first = document.querySelector<HTMLElement>(FOCUSABLE);
    const skip = screen.getByRole('link', { name: 'Saltar al contenido' });
    expect(first).toBe(skip);

    act(() => skip.click());

    const main = screen.getByRole('main');
    expect(main).toHaveAttribute('id', 'main');
    expect(document.activeElement).toBe(main);
  });

  it.each([
    ['es', 'Idioma'],
    ['ca', 'Llengua'],
  ] as const)(
    '[frontend_i18n.AC-04] shows the language selector in the header (%s)',
    (language, label) => {
      renderLayout(language);

      const banner = screen.getByRole('banner');
      expect(within(banner).getByRole('combobox', { name: label })).toBeInTheDocument();
      expect(within(banner).getByText('AvisaBus')).toBeInTheDocument();
    },
  );

  it.each([
    ['es', 'Datos: EMT València (GTFS y tiempos de llegada) · Ajuntament de València'],
    ['ca', "Dades: EMT València (GTFS i temps d'arribada) · Ajuntament de València"],
  ] as const)(
    '[frontend_i18n.AC-14] shows the data attribution in the footer (%s)',
    (language, text) => {
      renderLayout(language);

      expect(within(screen.getByRole('contentinfo')).getByText(text)).toBeInTheDocument();
    },
  );

  it('[frontend_i18n.AC-12] mounts exactly one pair of announcement regions', () => {
    renderLayout();

    expect(screen.getAllByRole('status')).toHaveLength(1);
    expect(screen.getAllByRole('alert')).toHaveLength(1);
  });

  it('[frontend_i18n.AC-17] follows the design structure: dividers and 640 px centred content', () => {
    renderLayout();

    expect(screen.getByRole('banner')).toHaveClass('border-b', 'border-divider');
    expect(screen.getByRole('contentinfo')).toHaveClass('border-t', 'border-divider');
    expect(screen.getByRole('main')).toHaveClass('max-w-[640px]', 'mx-auto', 'px-4', 'pt-5');
    expect(within(screen.getByRole('contentinfo')).getByText(/EMT/)).toHaveClass(
      'text-[13px]',
      'text-text-muted',
    );
  });
});
