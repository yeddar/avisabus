/**
 * Names for the API types generated from the backend OpenAPI document (`npm run gen:api`,
 * ADR-010). schema.d.ts is generated: never edit it by hand.
 */
import type { components } from './schema';

type Schemas = components['schemas'];

export type StopResponse = Schemas['StopResponse'];
export type StopLine = Schemas['StopLineSchema'];
export type StopArrivalsResponse = Schemas['StopArrivalsResponse'];
export type Arrival = Schemas['ArrivalSchema'];
export type Occupancy = Schemas['OccupancySchema'];
export type OccupancyLevel = Occupancy['level'];
export type Vehicle = Schemas['VehicleSchema'];
export type ArrivalKind = Arrival['kind'];
export type ArrivalSource = StopArrivalsResponse['source'];
export type Problem = Schemas['ProblemSchema'];
export type PositionResponse = Schemas['VehiclePositionResponse'];
export type PositionArrival = Schemas['PositionArrivalSchema'];
export type PositionStatus = PositionResponse['status'];
export type ShapeResponse = Schemas['ShapeResponse'];
export type Alert = Schemas['AlertSchema'];
export type AlertStatus = Alert['status'];
export type Need = Schemas['Need'];
export type CreateAlertRequest = Schemas['CreateAlertRequest'];
export type MyAlertsResponse = Schemas['MyAlertsResponse'];
