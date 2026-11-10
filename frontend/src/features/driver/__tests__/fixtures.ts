import type { Departure, DriverLine, DriverService, DriverView, StopDemand } from '../types';

export const LINE_93: DriverLine = {
  line: '93',
  color: 'FE0000',
  text_color: 'FFFFFF',
  directions: [
    { direction_id: 0, headsign: 'Passeig Marítim - Hospital Malva-rosa' },
    { direction_id: 1, headsign: 'Av. del Cid' },
  ],
};

export const DEPARTURE_FREE: Departure = {
  trip_id: '12345',
  service_date: '2026-11-09',
  departure_at: '2026-11-09T07:40:00Z',
  first_stop_name: 'Hospital Malva-rosa',
  headsign: 'Passeig Marítim - Hospital Malva-rosa',
  taken: false,
};

export const DEPARTURE_TAKEN: Departure = {
  ...DEPARTURE_FREE,
  trip_id: '12346',
  departure_at: '2026-11-09T07:55:00Z',
  taken: true,
};

export const SERVICE: DriverService = {
  line: '93',
  direction_id: 0,
  headsign: 'Passeig Marítim - Hospital Malva-rosa',
  trip_id: '12345',
  service_date: '2026-11-09',
  departure_at: '2026-11-09T07:40:00Z',
  color: 'FE0000',
  text_color: 'FFFFFF',
};

export function stopDemand(overrides: Partial<StopDemand> = {}): StopDemand {
  return {
    stop_id: '508',
    name: 'Parada 508',
    stop_sequence: 12,
    distance_m: 640,
    waiting: 0,
    needs: { RAMP: 0, EXTRA_TIME: 0, SEAT: 0, VISUAL: 0 },
    alert_ids: [],
    ...overrides,
  };
}

export function driverView(overrides: Partial<DriverView> = {}): DriverView {
  return {
    generated_at: '2026-11-09T07:41:00Z',
    service: SERVICE,
    gps: 'OK',
    off_route: false,
    finished: false,
    stops: [],
    total_waiting: 0,
    free_places: 30,
    free_seats: 4,
    capacity_alert: false,
    seat_alert: false,
    ...overrides,
  };
}
