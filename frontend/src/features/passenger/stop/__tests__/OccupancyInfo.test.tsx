import { describe, expect, it } from 'vitest';

import type { Occupancy } from '../../../../shared/api/types';
import { renderWithProviders } from '../../../../test/render';
import { OccupancyInfo } from '../OccupancyInfo';

const FREE: Occupancy = { level: 'FREE', has_free_seats: true, free_seats: 20 };
const MEDIUM: Occupancy = { level: 'MEDIUM', has_free_seats: true, free_seats: 6 };
const FULL: Occupancy = { level: 'FULL', has_free_seats: false, free_seats: 0 };
const MEDIUM_NO_SEATS: Occupancy = { level: 'MEDIUM', has_free_seats: false, free_seats: 0 };

function filledSilhouettes(container: HTMLElement): number {
  return container.querySelectorAll('svg [data-silhouette="filled"]').length;
}

describe('OccupancyInfo', () => {
  it.each([
    ['es', FREE, 'Poco ocupado', 'hay asientos libres', 1],
    ['es', MEDIUM, 'Ocupación media', 'hay asientos libres', 2],
    ['es', FULL, 'Lleno', 'sin asientos libres', 3],
    ['es', MEDIUM_NO_SEATS, 'Ocupación media', 'sin asientos libres', 2],
    ['ca', FREE, 'Poc ocupat', 'hi ha seients lliures', 1],
    ['ca', MEDIUM, 'Ocupació mitjana', 'hi ha seients lliures', 2],
    ['ca', FULL, 'Ple', 'sense seients lliures', 3],
  ] as const)(
    '[passenger_stop_view.AC-07] shows icon and text, never colour alone (%s, %o)',
    (language, occupancy, level, seats, filled) => {
      const { container, getByText } = renderWithProviders(
        <OccupancyInfo occupancy={occupancy} />,
        { language },
      );

      expect(getByText(level).tagName).toBe('STRONG');
      expect(getByText(seats)).toBeInTheDocument();
      expect(container.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
      expect(filledSilhouettes(container)).toBe(filled);
      expect(container.querySelectorAll('svg [data-silhouette]')).toHaveLength(3);
    },
  );

  it.each([
    ['es', 'Ocupación no disponible'],
    ['ca', 'Ocupació no disponible'],
  ] as const)(
    '[passenger_stop_view.AC-07] says "%s" when the occupancy is null',
    (language, text) => {
      const { container, getByText } = renderWithProviders(<OccupancyInfo occupancy={null} />, {
        language,
      });

      expect(getByText(text)).toBeInTheDocument();
      expect(filledSilhouettes(container)).toBe(0);
      expect(container.querySelectorAll('svg [data-silhouette="outline"]')).toHaveLength(3);
    },
  );

  it.each([
    [FREE, 'bg-occ-free-bg', 'text-occ-free-fg'],
    [MEDIUM, 'bg-occ-medium-bg', 'text-occ-medium-fg'],
    [FULL, 'bg-occ-full-bg', 'text-occ-full-fg'],
    [null, 'bg-occ-none-bg', 'text-occ-none-fg'],
  ])(
    '[passenger_stop_view.AC-07] uses the colours of docs/design.md §4 as reinforcement (%o)',
    (occupancy, bg, fg) => {
      const { container } = renderWithProviders(<OccupancyInfo occupancy={occupancy} />);

      expect(container.firstElementChild).toHaveClass(bg, fg);
    },
  );
});
