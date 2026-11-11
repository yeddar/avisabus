/**
 * Simulated API responses for the e2e tests, typed with the generated contract
 * (src/shared/api/types.ts): if the OpenAPI document changes, `tsc` reports the fixtures that no
 * longer match. Data from the examples of specs/stop_arrivals_api/design.md §3 (stop 508).
 *
 * Position and shape (passenger_map_view): the same files as src/test/fixtures/api — answers of
 * the real backend, verbatim (line 93, direction 0, shape 994_488_2271); the positions (v1.3,
 * `distance_to_stop_m` in real metres) with the SAE replayed and the clock fixed on 2026-11-04 (see
 * src/test/fixtures/api/index.ts).
 *
 * Alert (passenger_alert_ui): the example of specs/alert_create/design.md §3 for the 93 bus of
 * `arrivals-realtime` that arrives in 4 min (trip 12345).
 */
import type {
  Alert,
  PositionResponse,
  Problem,
  ShapeResponse,
  StopArrivalsResponse,
  StopResponse,
} from '../../src/shared/api/types';
import alert93 from './alert-93.json' with { type: 'json' };
import arrivalsEmpty from './arrivals-empty.json' with { type: 'json' };
import arrivalsRealtime from './arrivals-realtime.json' with { type: 'json' };
import arrivalsScheduled from './arrivals-scheduled.json' with { type: 'json' };
import lineNotAtStop from './line-not-at-stop.json' with { type: 'json' };
import networkUnavailable from './network-unavailable.json' with { type: 'json' };
import notFound from './not-found.json' with { type: 'json' };
import positionEnRoute from './position-en-route.json' with { type: 'json' };
import positionNoArrival from './position-no-arrival.json' with { type: 'json' };
import positionNotStarted from './position-not-started.json' with { type: 'json' };
import shape93 from './shape-93.json' with { type: 'json' };
import stop508 from './stop-508.json' with { type: 'json' };

/** Type of a value of `T` read from JSON: string literal unions become plain strings. */
type Json<T> = T extends string
  ? string
  : T extends (infer U)[]
    ? Json<U>[]
    : T extends object
      ? { [K in keyof T]: Json<T[K]> }
      : T;

const typed = <T>(value: Json<T>): T => value as T;

export const STOP_508 = typed<StopResponse>(stop508);
export const ARRIVALS_REALTIME = typed<StopArrivalsResponse>(arrivalsRealtime);
export const ARRIVALS_SCHEDULED = typed<StopArrivalsResponse>(arrivalsScheduled);
export const ARRIVALS_EMPTY = typed<StopArrivalsResponse>(arrivalsEmpty);
export const NOT_FOUND = typed<Problem>(notFound);
export const NETWORK_UNAVAILABLE = typed<Problem>(networkUnavailable);
export const LINE_NOT_AT_STOP = typed<Problem>(lineNotAtStop);
export const POSITION_EN_ROUTE = typed<PositionResponse>(positionEnRoute);
export const POSITION_NOT_STARTED = typed<PositionResponse>(positionNotStarted);
export const POSITION_NO_ARRIVAL = typed<PositionResponse>(positionNoArrival);
export const SHAPE_93 = typed<ShapeResponse>(shape93);
export const ALERT_93 = typed<Alert>(alert93);
