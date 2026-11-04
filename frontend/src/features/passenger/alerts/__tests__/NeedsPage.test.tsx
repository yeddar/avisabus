import { fireEvent, screen, waitFor } from '@testing-library/react';
import { RouterProvider, createMemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { routes } from '../../../../app/routes';
import { setNeedsProfile } from '../../../../shared/device/needsProfile';
import type { Language } from '../../../../shared/i18n/languages';
import { renderWithProviders } from '../../../../test/render';

const TEXTS = {
  es: {
    title: 'Mis necesidades',
    documentTitle: 'Mis necesidades · AvisaBus',
    needs: [
      'Necesito la rampa',
      'Necesito más tiempo para subir',
      'Necesito un asiento',
      'Tengo discapacidad visual',
    ],
    save: 'Guardar',
    clear: 'Borrar mis necesidades',
    saved: 'Necesidades guardadas',
    cleared: 'Necesidades borradas',
  },
  ca: {
    title: 'Les meues necessitats',
    documentTitle: 'Les meues necessitats · AvisaBus',
    needs: [
      'Necessite la rampa',
      'Necessite més temps per a pujar',
      'Necessite un seient',
      'Tinc discapacitat visual',
    ],
    save: 'Guarda',
    clear: 'Esborra les meues necessitats',
    saved: 'Necessitats guardades',
    cleared: 'Necessitats esborrades',
  },
} as const;

function renderNeeds(language: Language = 'es') {
  const router = createMemoryRouter(routes, { initialEntries: ['/necesidades'] });
  return renderWithProviders(<RouterProvider router={router} />, { language });
}

function politeRegion(): HTMLElement {
  const region = document.querySelector<HTMLElement>('[aria-live="polite"]');
  if (region === null) throw new Error('no polite region');
  return region;
}

describe('NeedsPage', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
    localStorage.clear();
    document.title = '';
  });

  it.each(['es', 'ca'] as const)(
    '[passenger_alert_ui.AC-02] offers the four needs, "Guardar" and "Borrar mis necesidades" (%s)',
    (language) => {
      const texts = TEXTS[language];
      renderNeeds(language);

      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(texts.title);
      expect(document.title).toBe(texts.documentTitle);
      const boxes = screen.getAllByRole('checkbox');
      expect(boxes).toHaveLength(4);
      texts.needs.forEach((label, index) => {
        expect(screen.getByRole('checkbox', { name: label })).toBe(boxes[index]);
        expect(boxes[index]).not.toBeChecked();
      });
      expect(screen.getByRole('button', { name: texts.save })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: texts.clear })).toBeInTheDocument();
    },
  );

  it('[passenger_alert_ui.AC-02] shows the stored profile checked', () => {
    setNeedsProfile(['RAMP', 'VISUAL']);

    renderNeeds();

    expect(screen.getByRole('checkbox', { name: 'Necesito la rampa' })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'Tengo discapacidad visual' })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'Necesito un asiento' })).not.toBeChecked();
  });

  it.each(['es', 'ca'] as const)(
    '[passenger_alert_ui.AC-02] "Guardar" keeps the profile only on the device and announces it politely (%s)',
    async (language) => {
      const texts = TEXTS[language];
      renderNeeds(language);

      fireEvent.click(screen.getByRole('checkbox', { name: texts.needs[2] }));
      fireEvent.click(screen.getByRole('checkbox', { name: texts.needs[0] }));
      fireEvent.click(screen.getByRole('button', { name: texts.save }));

      expect(localStorage.getItem('avisabus.needsProfile')).toBe('["RAMP","SEAT"]');
      await waitFor(() => expect(politeRegion()).toHaveTextContent(texts.saved));
      expect(fetchMock).not.toHaveBeenCalled();
    },
  );

  it.each(['es', 'ca'] as const)(
    '[passenger_alert_ui.AC-02] "Borrar mis necesidades" removes the profile, unchecks every need and announces it (%s)',
    async (language) => {
      const texts = TEXTS[language];
      setNeedsProfile(['EXTRA_TIME', 'SEAT']);
      renderNeeds(language);

      fireEvent.click(screen.getByRole('button', { name: texts.clear }));

      expect(localStorage.getItem('avisabus.needsProfile')).toBeNull();
      screen.getAllByRole('checkbox').forEach((box) => expect(box).not.toBeChecked());
      await waitFor(() => expect(politeRegion()).toHaveTextContent(texts.cleared));
      expect(fetchMock).not.toHaveBeenCalled();
    },
  );

  it('[passenger_alert_ui.AC-02] the needs are grouped with a legend', () => {
    renderNeeds();

    expect(screen.getByRole('group', { name: '¿Necesitas algo al subir?' })).toBeInTheDocument();
  });
});
