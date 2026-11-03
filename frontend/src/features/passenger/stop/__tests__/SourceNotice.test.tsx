import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { renderWithProviders } from '../../../../test/render';
import { SourceNotice } from '../SourceNotice';

describe('SourceNotice', () => {
  it.each([
    [
      'es',
      'Sin datos en tiempo real: se muestra el horario programado',
      'Sin datos en tiempo real:',
    ],
    ['ca', "Sense dades en temps real: es mostra l'horari programat", 'Sense dades en temps real:'],
  ] as const)(
    '[passenger_stop_view.AC-09] announces the scheduled timetable as a status (%s)',
    (language, text, bold) => {
      renderWithProviders(<SourceNotice source="SCHEDULED" />, { language });

      const strong = screen.getByText(bold);
      expect(strong.tagName).toBe('STRONG');
      const status = strong.closest('[role="status"]');
      expect(status).not.toBeNull();
      expect(status).toHaveTextContent(text);
    },
  );

  it('[passenger_stop_view.AC-09] shows nothing with real-time data', () => {
    renderWithProviders(<SourceNotice source="REALTIME" />);

    expect(screen.queryByText(/Sin datos en tiempo real/)).toBeNull();
    // Only the shared announcer regions remain.
    expect(screen.getAllByRole('status').every((el) => el.textContent === '')).toBe(true);
  });
});
