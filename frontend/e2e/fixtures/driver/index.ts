/**
 * Simulated answers of the driver API for e2e/driver.spec.ts (driver_ui.AC-11), typed with the
 * generated contract (src/features/driver/types.ts): `view.json` follows the example of
 * specs/driver_demand/design.md §3; `lines.json` and `departures.json` those of
 * specs/driver_session/design.md §3.
 */
import type {
  DeparturesResponse,
  DriverView,
  LinesResponse,
} from '../../../src/features/driver/types';
import departures from './departures.json' with { type: 'json' };
import lines from './lines.json' with { type: 'json' };
import view from './view.json' with { type: 'json' };

export const DRIVER_LINES = lines as LinesResponse;
export const DRIVER_DEPARTURES = departures as DeparturesResponse;
export const DRIVER_VIEW = view as DriverView;
