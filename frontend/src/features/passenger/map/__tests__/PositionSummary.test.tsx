import { screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { Language } from '../../../../shared/i18n/languages';
import { renderWithProviders } from '../../../../test/render';
import { PositionSummary } from '../PositionSummary';
import type { Summary } from '../summary';

const EN_ROUTE: Summary = {
  text: 'El autobús está a <strong>3,4 km</strong> de tu parada, <strong>a 3 paradas</strong>. Próxima parada: <name>Cid - Hospital General</name>. Llega en <strong>5 minutos</strong>.',
  badge: 'estimated',
};

function renderSummary(summary: Summary, language: Language = 'es') {
  renderWithProviders(<PositionSummary summary={summary} textId="summary-text" />, { language });
  return screen.getByRole('region');
}

describe('PositionSummary', () => {
  it('[passenger_map_view.AC-04] is a region titled "Dónde está el autobús" with the summary text', () => {
    const region = renderSummary(EN_ROUTE);

    expect(region).toHaveAccessibleName('Dónde está el autobús');
    expect(within(region).getByRole('heading', { level: 2 })).toHaveTextContent(
      'Dónde está el autobús',
    );
    const text = document.getElementById('summary-text');
    expect(text).toHaveTextContent(
      'El autobús está a 3,4 km de tu parada, a 3 paradas. Próxima parada: Cid - Hospital General. Llega en 5 minutos.',
    );
  });

  it('[passenger_map_view.AC-04] shows distance, stops and time in bold and the stop name in Valencian', () => {
    renderSummary(EN_ROUTE);

    const bold = document.querySelectorAll('#summary-text strong');
    expect([...bold].map((node) => node.textContent)).toEqual([
      '3,4 km',
      'a 3 paradas',
      '5 minutos',
    ]);
    expect(screen.getByText('Cid - Hospital General')).toHaveAttribute('lang', 'ca-ES-valencia');
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
});
