import { afterEach, describe, expect, it, vi } from 'vitest';

import type { Arrival } from '../../../../shared/api/types';
import type { Language } from '../../../../shared/i18n/languages';
import { ARRIVALS_REALTIME } from '../../../../test/fixtures/api';
import { renderWithProviders } from '../../../../test/render';
import { useArrivingAnnouncements } from '../useArrivingAnnouncements';

const announce = vi.fn();

vi.mock('../../../../shared/ui/Announcer', () => ({
  AnnouncerProvider: ({ children }: { children: React.ReactNode }) => children,
  useAnnounce: () => announce,
}));

const T0 = Date.parse('2026-11-04T07:40:00Z');
const at = (seconds: number) => new Date(T0 + seconds * 1000);
const iso = (seconds: number) => at(seconds).toISOString();

/** Line 93 towards the GTFS headsign; the SAE text is the abbreviated one. */
function bus93(minutes: number, tripId: string | null = 'trip-A', offsetS = 0): Arrival {
  const base = ARRIVALS_REALTIME().arrivals[1]!;
  return {
    ...base,
    minutes,
    arrival_at: iso(offsetS + minutes * 60),
    vehicle: tripId === null ? null : { trip_id: tripId, service_date: '2026-11-04' },
  };
}

function Probe({ arrivals, now }: { arrivals: Arrival[]; now: Date }) {
  useArrivingAnnouncements(arrivals, now);
  return null;
}

function setup(arrivals: Arrival[], now: Date, language: Language = 'es') {
  const view = renderWithProviders(<Probe arrivals={arrivals} now={now} />, { language });
  return (next: Arrival[], nextNow: Date) => view.rerender(<Probe arrivals={next} now={nextNow} />);
}

const ARRIVING_93 = 'Línea 93 hacia Passeig Marítim - Hospital Malva-rosa está llegando';

describe('useArrivingAnnouncements', () => {
  afterEach(() => {
    announce.mockReset();
  });

  it('[passenger_stop_view.AC-15] announces once, politely, when the first 93 passes to "Llegando" with the countdown', () => {
    const arrivals = [bus93(1)];
    const update = setup(arrivals, at(0));
    update(arrivals, at(45));
    expect(announce).not.toHaveBeenCalled();

    update(arrivals, at(60));
    expect(announce).toHaveBeenCalledTimes(1);
    expect(announce).toHaveBeenCalledWith(ARRIVING_93, 'polite');

    update(arrivals, at(75));
    update([bus93(0, 'trip-A', 80)], at(80));
    expect(announce).toHaveBeenCalledTimes(1);
  });

  it('[passenger_stop_view.AC-15] announces when a refresh brings the first arrival at 0 minutes', () => {
    const update = setup([bus93(2)], at(0));

    update([bus93(0, 'trip-A', 20)], at(20));

    expect(announce).toHaveBeenCalledExactlyOnceWith(ARRIVING_93, 'polite');
  });

  it('[passenger_stop_view.AC-15] stays silent on routine refreshes', () => {
    const update = setup([bus93(5), bus93(12, 'trip-B')], at(0));

    update([bus93(4, 'trip-A', 20), bus93(11, 'trip-B', 20)], at(20));
    update([bus93(4, 'trip-A', 40)], at(40));
    update([], at(60));

    expect(announce).not.toHaveBeenCalled();
  });

  it('[passenger_stop_view.AC-15] does not announce buses that were already arriving when the data first appear', () => {
    const update = setup([bus93(0)], at(0));
    update([bus93(0, 'trip-A', 20)], at(20));

    expect(announce).not.toHaveBeenCalled();
  });

  it('[passenger_stop_view.AC-15] only considers the first arrival of each line and destination', () => {
    const update = setup([bus93(1), bus93(1, 'trip-B')], at(0));

    update([bus93(0, 'trip-A', 60), bus93(0, 'trip-B', 60)], at(60));

    expect(announce).toHaveBeenCalledExactlyOnceWith(ARRIVING_93, 'polite');
  });

  it('[passenger_stop_view.AC-15] announces each line and destination arriving at the same time', () => {
    const alboraia: Arrival = {
      ...ARRIVALS_REALTIME().arrivals[0]!,
      minutes: 1,
      arrival_at: iso(60),
    };
    const update = setup([alboraia, bus93(1)], at(0));

    update([alboraia, bus93(1)], at(60));

    expect(announce).toHaveBeenCalledExactlyOnceWith(
      `Línea 70 hacia Alboraia está llegando. ${ARRIVING_93}`,
      'polite',
    );
  });

  it('[passenger_stop_view.AC-15] announces only once a bus without vehicle whose arrival_at moves with each refresh', () => {
    const update = setup([bus93(1, null)], at(0));

    update([bus93(0, null, 20)], at(20));
    update([bus93(0, null, 40)], at(40));
    update([bus93(0, null, 60)], at(60));

    expect(announce).toHaveBeenCalledTimes(1);
  });

  it('[passenger_stop_view.AC-15] announces the next bus of the same line when it arrives too', () => {
    const update = setup([bus93(1), bus93(9, 'trip-B')], at(0));
    update([bus93(0, 'trip-A', 60), bus93(8, 'trip-B', 60)], at(60));
    expect(announce).toHaveBeenCalledTimes(1);

    // Bus A has passed; bus B becomes the first one and later arrives.
    update([bus93(1, 'trip-B', 420)], at(420));
    update([bus93(0, 'trip-B', 480)], at(480));

    expect(announce).toHaveBeenCalledTimes(2);
  });

  it('[passenger_stop_view.AC-15] never announces clock-time arrivals, which never show "Llegando"', () => {
    const night: Arrival = { ...ARRIVALS_REALTIME().arrivals[4]!, arrival_at: iso(60) };
    const update = setup([night], at(0));

    update([night], at(120));

    expect(announce).not.toHaveBeenCalled();
  });

  it('[passenger_stop_view.AC-15] speaks the GTFS headsign in the interface language', () => {
    const update = setup([bus93(1)], at(0), 'ca');

    update([bus93(1)], at(60));

    expect(announce).toHaveBeenCalledExactlyOnceWith(
      'Línia 93 cap a Passeig Marítim - Hospital Malva-rosa està arribant',
      'polite',
    );
  });
});
