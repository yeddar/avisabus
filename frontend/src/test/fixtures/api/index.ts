/**
 * API responses for component tests, typed with the generated contract (shared/api/types.ts):
 * if the OpenAPI document changes, `tsc` reports the fixtures that no longer match. Data from
 * the examples of specs/stop_arrivals_api/design.md §3 (stop 508).
 *
 * Position and shape (passenger_map_view): answers of the real backend over `gtfs_mini` and the
 * `stop_508_peak` replay (line 93, direction 0, shape 994_488_2271), with the dates moved to
 * 2026-11-04 08:40 in València. `position-not-started` (scheduled, clock time, bus at the first
 * stop) and `position-no-arrival` are derived from `position-en-route`.
 */
import type {
  PositionResponse,
  ShapeResponse,
  StopArrivalsResponse,
  StopResponse,
} from '../../../shared/api/types';
import arrivalsEmpty from './arrivals-empty.json';
import arrivalsRealtime from './arrivals-realtime.json';
import arrivalsScheduled from './arrivals-scheduled.json';
import positionEnRoute from './position-en-route.json';
import positionNoArrival from './position-no-arrival.json';
import positionNotStarted from './position-not-started.json';
import shape93 from './shape-93.json';
import stop508 from './stop-508.json';

/** Type of a value of `T` read from JSON: string literal unions become plain strings. */
type Json<T> = T extends string
  ? string
  : T extends (infer U)[]
    ? Json<U>[]
    : T extends object
      ? { [K in keyof T]: Json<T[K]> }
      : T;

function typed<T>(value: Json<T>): T {
  return structuredClone(value) as T;
}

export const STOP_508 = (): StopResponse => typed<StopResponse>(stop508);
export const ARRIVALS_REALTIME = (): StopArrivalsResponse =>
  typed<StopArrivalsResponse>(arrivalsRealtime);
export const ARRIVALS_SCHEDULED = (): StopArrivalsResponse =>
  typed<StopArrivalsResponse>(arrivalsScheduled);
export const ARRIVALS_EMPTY = (): StopArrivalsResponse =>
  typed<StopArrivalsResponse>(arrivalsEmpty);
export const POSITION_EN_ROUTE = (): PositionResponse => typed<PositionResponse>(positionEnRoute);
export const POSITION_NOT_STARTED = (): PositionResponse =>
  typed<PositionResponse>(positionNotStarted);
export const POSITION_NO_ARRIVAL = (): PositionResponse =>
  typed<PositionResponse>(positionNoArrival);
export const SHAPE_93 = (): ShapeResponse => typed<ShapeResponse>(shape93);
