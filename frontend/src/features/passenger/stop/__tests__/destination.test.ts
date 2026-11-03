import { describe, expect, it } from 'vitest';

import { ARRIVALS_REALTIME, ARRIVALS_SCHEDULED } from '../../../../test/fixtures/api';
import { spokenDestination, visibleDestination } from '../destination';

describe('destination', () => {
  it('[passenger_stop_view.AC-05] shows the SAE text and speaks the GTFS headsign (real time, direction resolved)', () => {
    const arrival = ARRIVALS_REALTIME().arrivals[1]!;

    expect(visibleDestination(arrival)).toBe('Pass. Marítim');
    expect(spokenDestination(arrival)).toBe('Passeig Marítim - Hospital Malva-rosa');
  });

  it('[passenger_stop_view.AC-05] uses the SAE text for both when the direction is not resolved', () => {
    const arrival = ARRIVALS_REALTIME().arrivals[2]!;

    expect(visibleDestination(arrival)).toBe('Pl. Ajuntament');
    expect(spokenDestination(arrival)).toBe('Pl. Ajuntament');
  });

  it('[passenger_stop_view.AC-05] uses the headsign on screen when there is no SAE text (scheduled)', () => {
    const arrival = ARRIVALS_SCHEDULED().arrivals[0]!;

    expect(visibleDestination(arrival)).toBe('Passeig Marítim - Hospital Malva-rosa');
    expect(spokenDestination(arrival)).toBe('Passeig Marítim - Hospital Malva-rosa');
  });
});
