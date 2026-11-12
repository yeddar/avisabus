import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { Language } from '../../../../shared/i18n/languages';
import { renderWithProviders } from '../../../../test/render';
import { PositionSummary } from '../PositionSummary';
import type { Summary } from '../summary';

const EN_ROUTE: Summary = {
  text: 'El autobús está a <strong>844 m</strong> de tu parada, <strong>a 2 paradas</strong>. Próxima parada: <name>Cid - Josep Maestre</name>. Llega en <strong>5 minutos</strong>.',
  badge: 'estimated',
};

function renderSummary(summary: Summary, language: Language = 'es') {
  renderWithProviders(<PositionSummary summary={summary} />, { language });
  return screen.getByRole('region');
}

describe('PositionSummary', () => {
  it('[passenger_map_view.AC-04] is a region titled "Dónde está el autobús" with the summary text', () => {
    const region = renderSummary(EN_ROUTE);

    expect(region).toHaveAccessibleName('Dónde está el autobús');
    expect(within(region).getByRole('heading', { level: 2 })).toHaveTextContent(
      'Dónde está el autobús',
    );
    expect(within(region).getByText(/^El autobús/)).toHaveTextContent(
      'El autobús está a 844 m de tu parada, a 2 paradas. Próxima parada: Cid - Josep Maestre. Llega en 5 minutos.',
    );
  });

  it('[passenger_map_view.AC-04] shows distance, stops and time in bold and the stop name in Valencian', () => {
    renderSummary(EN_ROUTE);

    const bold = screen.getByRole('region').querySelectorAll('p strong');
    expect([...bold].map((node) => node.textContent)).toEqual([
      '844 m',
      'a 2 paradas',
      '5 minutos',
    ]);
    expect(screen.getByText('Cid - Josep Maestre')).toHaveAttribute('lang', 'ca-ES-valencia');
  });

  it('[passenger_map_view.AC-06] is not a live region: refreshes are not read out', () => {
    const region = renderSummary(EN_ROUTE);

    expect(region.closest('[aria-live]')).toBeNull();
    expect(region.querySelector('[aria-live], [role="status"], [role="alert"]')).toBeNull();
  });

  it.each([
    ['es', 'estimated', 'Posición estimada'],
    ['es', 'scheduled', 'Posición según horario'],
    ['ca', 'estimated', 'Posició estimada'],
    ['ca', 'scheduled', "Posició segons l'horari"],
  ] as const)('[passenger_map_view.AC-05] (%s) badge "%s" says "%s"', (language, badge, text) => {
    const region = renderSummary({ ...EN_ROUTE, badge }, language);

    expect(within(region).getByText(text)).toBeVisible();
  });

  it.each([
    [
      'es',
      'Posición no disponible en este momento. No hay llegadas previstas de esta línea en tu parada.',
    ],
    [
      'ca',
      "Posició no disponible en este moment. No hi ha arribades previstes d'esta línia en la teua parada.",
    ],
  ] as const)(
    '[passenger_map_view.AC-05] (v1.2, %s) without a position there is no badge',
    (language, text) => {
      const region = renderSummary({ text, badge: null }, language);

      expect(within(region).getByText(text)).toBeVisible();
      for (const badge of [
        'Posición estimada',
        'Posición según horario',
        'Posició estimada',
        "Posició segons l'horari",
      ]) {
        expect(within(region).queryByText(badge)).toBeNull();
      }
      // Only the heading and the text are left: no empty badge box either.
      expect([...region.children].map((child) => child.tagName)).toEqual(['H2', 'P']);
    },
  );
});
