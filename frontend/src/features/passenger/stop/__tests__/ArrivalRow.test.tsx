import { screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { ARRIVALS_REALTIME, ARRIVALS_SCHEDULED } from '../../../../test/fixtures/api';
import { renderWithProviders } from '../../../../test/render';
import { ArrivalRow } from '../ArrivalRow';
import { spokenText, visualPart } from './helpers';

const NOW = new Date('2026-11-04T07:40:00Z');
const TOKEN = 'AbCdEfGhIjKlMnOpQrStUv';

function renderRow(index: number, { scheduled = false, language = 'es' as 'es' | 'ca' } = {}) {
  const arrivals = scheduled ? ARRIVALS_SCHEDULED().arrivals : ARRIVALS_REALTIME().arrivals;
  renderWithProviders(
    <MemoryRouter>
      <ul>
        <ArrivalRow
          arrival={arrivals[index]!}
          now={NOW}
          scheduled={scheduled}
          stopId="508"
          token={TOKEN}
        />
      </ul>
    </MemoryRouter>,
    { language },
  );
  return screen.getByRole('listitem');
}

describe('ArrivalRow', () => {
  it('[passenger_stop_view.AC-05] real time with resolved direction: SAE text on screen, headsign in the spoken sentence', () => {
    const item = renderRow(1);

    expect(spokenText(item)).toBe(
      'Línea 93, hacia Passeig Marítim - Hospital Malva-rosa, llega en 4 minutos, ocupación media, hay asientos libres',
    );
    const visual = visualPart(item);
    expect(visual).toHaveTextContent('93');
    expect(visual).toHaveTextContent('hacia');
    expect(visual).toHaveTextContent('Pass. Marítim');
    expect(visual).not.toHaveTextContent('Hospital Malva-rosa');
    expect(visual).toHaveTextContent('4 min');
    expect(visual).toHaveTextContent('Ocupación media');
    expect(visual).toHaveTextContent('hay asientos libres');
  });

  it('[passenger_stop_view.AC-05] real time without direction: the SAE text on screen and in the sentence', () => {
    const item = renderRow(2);

    expect(spokenText(item)).toBe(
      'Línea 70, hacia Pl. Ajuntament, llega en 9 minutos, ocupación no disponible',
    );
    expect(visualPart(item)).toHaveTextContent('Pl. Ajuntament');
    expect(visualPart(item)).toHaveTextContent('Ocupación no disponible');
  });

  it('[passenger_stop_view.AC-05] scheduled: the headsign on screen and in the sentence, marked as scheduled', () => {
    const item = renderRow(0, { scheduled: true });

    expect(spokenText(item)).toBe(
      'Línea 93, hacia Passeig Marítim - Hospital Malva-rosa, llega a las 08:52 según el horario programado, ocupación media, hay asientos libres',
    );
    expect(visualPart(item)).toHaveTextContent('Passeig Marítim - Hospital Malva-rosa');
    expect(visualPart(item)).toHaveTextContent('programado');
  });

  it('[passenger_stop_view.AC-05] reads the sentence in Valencian', () => {
    const item = renderRow(1, { language: 'ca' });

    expect(spokenText(item)).toBe(
      'Línia 93, cap a Passeig Marítim - Hospital Malva-rosa, arriba en 4 minuts, ocupació mitjana, hi ha seients lliures',
    );
  });

  it('[passenger_stop_view.AC-05] hides the visual content from screen readers and marks GTFS names as Valencian', () => {
    const item = renderRow(1);

    expect(visualPart(item)).toHaveAttribute('aria-hidden', 'true');
    const spokenDestination = screen.getByText('Passeig Marítim - Hospital Malva-rosa');
    expect(spokenDestination).toHaveAttribute('lang', 'ca-ES-valencia');
    expect(screen.getByText('Pass. Marítim')).toHaveAttribute('lang', 'ca-ES-valencia');
  });

  it('[passenger_stop_view.AC-05] says "está llegando" for an arrival at 0 minutes', () => {
    const item = renderRow(0);

    expect(spokenText(item)).toBe(
      'Línea 70, hacia Alboraia, está llegando, poco ocupado, hay asientos libres',
    );
    expect(visualPart(item)).toHaveTextContent('Llegando');
  });

  it('[passenger_stop_view.AC-07] reads a full bus as "lleno, sin asientos libres"', () => {
    const item = renderRow(3);

    expect(spokenText(item)).toMatch(/, lleno, sin asientos libres$/);
  });

  it('[passenger_stop_view.AC-08] shows an arrival outside the network with its time and without occupancy', () => {
    const item = renderRow(4);

    expect(spokenText(item)).toBe('Línea N4, hacia Est.del Nord, llega a las 09:41');
    const visual = visualPart(item);
    expect(visual).toHaveTextContent('09:41');
    expect(visual).not.toHaveTextContent(/ocupaci|asientos/i);
    expect(item.querySelector('svg [data-silhouette]')).toBeNull();
    expect(screen.queryByRole('button')).toBeNull();
    expect(screen.queryByRole('link')).toBeNull();
  });

  it('[passenger_map_view.AC-01] links an arrival in the network with a resolved direction to its map', () => {
    const item = renderRow(1);

    const link = within(item).getByRole('link', {
      name: 'Ver en el mapa la línea 93 hacia Passeig Marítim - Hospital Malva-rosa',
    });
    expect(link).toHaveTextContent('Ver en el mapa');
    expect(link).toHaveAttribute('href', `/p/508/map/93/0?t=${TOKEN}`);
    // Reachable by screen readers and keyboard: outside the aria-hidden visual part.
    expect(visualPart(item)).not.toContainElement(link);
  });

  it('[passenger_map_view.AC-01] links a scheduled arrival with a resolved direction too', () => {
    const item = renderRow(0, { scheduled: true });

    expect(within(item).getByRole('link')).toHaveAttribute('href', `/p/508/map/93/0?t=${TOKEN}`);
  });

  it('[passenger_map_view.AC-01] names the link in Valencian', () => {
    const item = renderRow(1, { language: 'ca' });

    const link = within(item).getByRole('link', {
      name: 'Mostra en el mapa la línia 93 cap a Passeig Marítim - Hospital Malva-rosa',
    });
    expect(link).toHaveTextContent('Mostra en el mapa');
  });

  it('[passenger_map_view.AC-01] has no map link without a resolved direction', () => {
    const item = renderRow(2);

    expect(within(item).queryByRole('link')).toBeNull();
  });

  it('[passenger_map_view.AC-01] has no map link outside the network', () => {
    const item = renderRow(4);

    expect(within(item).queryByRole('link')).toBeNull();
  });

  it('[passenger_map_view.AC-01] encodes the stop, the line and the token in the map URL', () => {
    const arrival = { ...ARRIVALS_REALTIME().arrivals[1]!, line: 'C/1', direction_id: 1 };
    renderWithProviders(
      <MemoryRouter>
        <ul>
          <ArrivalRow arrival={arrival} now={NOW} scheduled={false} stopId="5 08" token="a+b/c" />
        </ul>
      </MemoryRouter>,
    );

    expect(screen.getByRole('link')).toHaveAttribute('href', '/p/5%2008/map/C%2F1/1?t=a%2Bb%2Fc');
  });
});
