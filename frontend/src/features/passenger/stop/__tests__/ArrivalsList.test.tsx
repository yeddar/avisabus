import { screen, within } from '@testing-library/react';
import type { ReactElement } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { ARRIVALS_REALTIME, ARRIVALS_SCHEDULED } from '../../../../test/fixtures/api';
import { renderWithProviders } from '../../../../test/render';
import { ArrivalsList } from '../ArrivalsList';
import { spokenText } from './helpers';

const NOW = new Date('2026-11-04T07:40:00Z');
const STOP = { stopId: '508', token: 'AbCdEfGhIjKlMnOpQrStUv' };

/** The rows link to the map (passenger_map_view.AC-01), so they need a router. */
const inRouter = (ui: ReactElement) => <MemoryRouter>{ui}</MemoryRouter>;

describe('ArrivalsList', () => {
  it('[passenger_stop_view.AC-05] lists the arrivals in the API order', () => {
    const { arrivals, source } = ARRIVALS_REALTIME();

    renderWithProviders(
      inRouter(<ArrivalsList arrivals={arrivals} source={source} now={NOW} {...STOP} />),
    );

    const items = within(screen.getByRole('list')).getAllByRole('listitem');
    expect(items.map((item) => spokenText(item).split(',')[0])).toEqual([
      'Línea 70',
      'Línea 93',
      'Línea 70',
      'Línea 93',
      'Línea N4',
    ]);
  });

  it('[passenger_stop_view.AC-09] marks every time as scheduled when the source is SCHEDULED', () => {
    const { arrivals, source } = ARRIVALS_SCHEDULED();

    renderWithProviders(
      inRouter(<ArrivalsList arrivals={arrivals} source={source} now={NOW} {...STOP} />),
    );

    const items = screen.getAllByRole('listitem');
    expect(items).toHaveLength(2);
    for (const item of items) {
      expect(within(item).getByText('programado')).toBeInTheDocument();
      expect(spokenText(item)).toContain('según el horario programado');
    }
  });

  it.each([
    ['es', 'No hay llegadas previstas en este momento'],
    ['ca', 'No hi ha arribades previstes en este moment'],
  ] as const)('[passenger_stop_view.AC-10] says there are no arrivals (%s)', (language, text) => {
    renderWithProviders(
      inRouter(<ArrivalsList arrivals={[]} source="REALTIME" now={NOW} {...STOP} />),
      { language },
    );

    expect(screen.getByText(text)).toBeInTheDocument();
    expect(screen.queryByRole('list')).toBeNull();
  });
});
