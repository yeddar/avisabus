/** Names for the API types of the driver routes (generated from the backend OpenAPI document). */
import type { components } from '../../shared/api/schema';

type Schemas = components['schemas'];

export type DriverLine = Schemas['LineSchema'];
export type LinesResponse = Schemas['LinesResponse'];
export type Departure = Schemas['DepartureSchema'];
export type DeparturesResponse = Schemas['DeparturesResponse'];
export type DriverView = Schemas['DriverViewResponse'];
export type DriverService = Schemas['DriverServiceViewSchema'];
export type StopDemand = Schemas['StopDemandSchema'];
export type NeedCounts = Schemas['NeedCountsSchema'];
export type GpsState = Schemas['GpsState'];
