/**
 * Simulated API responses for the e2e tests, typed with the generated contract
 * (src/shared/api/types.ts): if the OpenAPI document changes, `tsc` reports the fixtures that no
 * longer match. Data from the examples of specs/stop_arrivals_api/design.md §3 (stop 508).
 */
import type { Problem, StopArrivalsResponse, StopResponse } from '../../src/shared/api/types';
import arrivalsEmpty from './arrivals-empty.json' with { type: 'json' };
import arrivalsRealtime from './arrivals-realtime.json' with { type: 'json' };
import arrivalsScheduled from './arrivals-scheduled.json' with { type: 'json' };
import networkUnavailable from './network-unavailable.json' with { type: 'json' };
import notFound from './not-found.json' with { type: 'json' };
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
