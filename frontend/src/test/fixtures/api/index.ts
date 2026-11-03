/**
 * API responses for component tests, typed with the generated contract (shared/api/types.ts):
 * if the OpenAPI document changes, `tsc` reports the fixtures that no longer match. Data from
 * the examples of specs/stop_arrivals_api/design.md §3 (stop 508).
 */
import type { StopArrivalsResponse, StopResponse } from '../../../shared/api/types';
import arrivalsEmpty from './arrivals-empty.json';
import arrivalsRealtime from './arrivals-realtime.json';
import arrivalsScheduled from './arrivals-scheduled.json';
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
