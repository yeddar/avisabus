import { afterEach, describe, expect, it, vi } from 'vitest';

import type { PositionResponse, PositionStatus } from '../../../../shared/api/types';
import type { Language } from '../../../../shared/i18n/languages';
import { POSITION_EN_ROUTE, POSITION_NO_ARRIVAL } from '../../../../test/fixtures/api';
import { renderWithProviders } from '../../../../test/render';
import { useProximityAnnouncements } from '../useProximityAnnouncements';

const announce = vi.fn();

vi.mock('../../../../shared/ui/Announcer', () => ({
  AnnouncerProvider: ({ children }: { children: React.ReactNode }) => children,
  useAnnounce: () => announce,
}));

const ONE_STOP = 'El autobús llegará a tu parada en la siguiente';
const ARRIVING = 'El autobús está llegando a tu parada';

/** A fresh answer (new object, as after every refresh) for a trip. */
function bus(stopsAway: number, status: PositionStatus = 'EN_ROUTE', tripId = 'trip-A') {
  const p = POSITION_EN_ROUTE();
  p.status = status;
  p.vehicle = { trip_id: tripId, service_date: '2026-11-04' };
  p.position = { ...p.position!, stops_away: stopsAway };
  return p;
}

function Probe({ position }: { position: PositionResponse | undefined }) {
  useProximityAnnouncements(position);
  return null;
}

function setup(position: PositionResponse | undefined, language: Language = 'es') {
  const view = renderWithProviders(<Probe position={position} />, { language });
  return (next: PositionResponse | undefined) => view.rerender(<Probe position={next} />);
}

describe('useProximityAnnouncements', () => {
  afterEach(() => {
    announce.mockReset();
  });

  it('[passenger_map_view.AC-06] routine refreshes are not announced', () => {
    const update = setup(bus(3));
    update(bus(3));
    update(bus(2));
    update(bus(1));
    update(POSITION_NO_ARRIVAL());

    expect(announce).not.toHaveBeenCalled();
  });

  it('[passenger_map_view.AC-06] announces once, politely, when stops_away passes to 0', () => {
    const update = setup(bus(2));
    update(bus(0));
    update(bus(0));
    update(bus(0));

    expect(announce).toHaveBeenCalledExactlyOnceWith(ONE_STOP, 'polite');
  });

  it('[passenger_map_view.AC-06] announces once, politely, when the status passes to AT_STOP', () => {
    const update = setup(bus(0));
    update(bus(0, 'AT_STOP'));
    update(bus(0, 'AT_STOP'));

    expect(announce).toHaveBeenCalledExactlyOnceWith(ARRIVING, 'polite');
  });

  it('[passenger_map_view.AC-06] announces each milestone once per trip, even if the estimate goes back', () => {
    const update = setup(bus(3));
    update(bus(0));
    update(bus(1)); // the SAE delays the bus
    update(bus(0));
    update(bus(0, 'AT_STOP'));
    update(bus(1));
    update(bus(0, 'AT_STOP'));

    expect(announce.mock.calls).toEqual([
      [ONE_STOP, 'polite'],
      [ARRIVING, 'polite'],
    ]);
  });

  it('[passenger_map_view.AC-06] a bus that reaches AT_STOP directly is only announced as arriving', () => {
    const update = setup(bus(2));
    update(bus(0, 'AT_STOP'));
    update(bus(0));

    expect(announce).toHaveBeenCalledExactlyOnceWith(ARRIVING, 'polite');
  });

  it('[passenger_map_view.AC-06] the next trip is announced again', () => {
    const update = setup(bus(0, 'AT_STOP', 'trip-A'));
    update(bus(4, 'EN_ROUTE', 'trip-B'));
    update(bus(0, 'EN_ROUTE', 'trip-B'));
    update(bus(0, 'AT_STOP', 'trip-B'));

    expect(announce.mock.calls).toEqual([
      [ONE_STOP, 'polite'],
      [ARRIVING, 'polite'],
    ]);
  });

  it('[passenger_map_view.AC-06] what the first data already show is not announced (the summary says it)', () => {
    const update = setup(undefined);
    update(bus(0, 'AT_STOP'));
    update(bus(0, 'AT_STOP'));

    expect(announce).not.toHaveBeenCalled();
  });

  it('[passenger_map_view.AC-06] announces in Valencian', () => {
    const update = setup(bus(1), 'ca');
    update(bus(0));
    update(bus(0, 'AT_STOP'));

    expect(announce.mock.calls).toEqual([
      ["L'autobús arribarà a la teua parada en la següent", 'polite'],
      ["L'autobús està arribant a la teua parada", 'polite'],
    ]);
  });
});
