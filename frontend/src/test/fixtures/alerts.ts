import type { Alert } from '../../shared/api/types';

/**
 * Alerts as returned by the API (alert_create design §3), for the buses of
 * fixtures/api/arrivals-realtime.json at stop 508: line 93 trips 12345 (4 min) and 12346
 * (16 min), line 70 trip 70_1_0740 (arriving).
 */
export function alertFixture(overrides: Partial<Alert> = {}): Alert {
  return {
    alert_id: '6f1c0d6e-3b9a-4c2e-9f4d-2a7b8c9d0e1f',
    stop_id: '508',
    stop_name: "Parc de l'Oest - Enguera",
    line: '93',
    direction_id: 0,
    destination: 'Passeig Marítim - Hospital Malva-rosa',
    trip_id: '12345',
    service_date: '2026-11-04',
    needs: ['RAMP', 'SEAT'],
    status: 'PENDING_DRIVER',
    created_at: '2026-11-04T07:40:00Z',
    expires_at: '2026-11-04T08:10:00Z',
    ...overrides,
  };
}

/** Line 70 alert for the bus that is arriving (trip 70_1_0740). */
export const alert70 = (overrides: Partial<Alert> = {}): Alert =>
  alertFixture({
    alert_id: '1b2c3d4e-5f60-4a7b-8c9d-0e1f2a3b4c5d',
    line: '70',
    destination: 'Alboraia',
    trip_id: '70_1_0740',
    needs: [],
    ...overrides,
  });
