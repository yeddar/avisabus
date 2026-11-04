import type { PositionResponse, ShapeResponse } from '../../../shared/api/types';
import { accessibleLineColors } from '../../../shared/color/contrast';

export type LatLng = [number, number];
export type Bounds = [LatLng, LatLng];

/** What the map draws (passenger_map_view.AC-07, AC-08), independent of Leaflet. */
export type MapModel = {
  line: { coords: LatLng[]; color: string }; // [lat, lon] for Leaflet
  stops: { id: string; name: string; latLng: LatLng; isTarget: boolean }[];
  bus: { latLng: LatLng; bearing: number | null; scheduled: boolean } | null;
  fitBounds: Bounds; // bus + stop, or the whole shape
};

/** Without a shape nor a position, the map frames a fixed box of 300 m around the stop. */
export const STOP_ONLY_HALF_SIZE_M = 150;
const METERS_PER_DEGREE_LAT = 111_320;
/** The line colour must stand out on the (light) map like text on white (docs/design.md §4). */
const MAP_BACKGROUND = 'FFFFFF';

function boundsOf(points: LatLng[]): Bounds {
  const lats = points.map(([lat]) => lat);
  const lons = points.map(([, lon]) => lon);
  return [
    [Math.min(...lats), Math.min(...lons)],
    [Math.max(...lats), Math.max(...lons)],
  ];
}

function boxAround([lat, lon]: LatLng, halfSizeM: number): Bounds {
  const dLat = halfSizeM / METERS_PER_DEGREE_LAT;
  const dLon = halfSizeM / (METERS_PER_DEGREE_LAT * Math.cos((lat * Math.PI) / 180));
  return [
    [lat - dLat, lon - dLon],
    [lat + dLat, lon + dLon],
  ];
}

/**
 * Layers of the map for a shape (null without shape_id or when it does not exist) and a
 * position answer. The passenger's stop is always drawn: from the shape, or from `position.stop`
 * when the shape does not list it.
 */
export function buildMapModel(shape: ShapeResponse | null, position: PositionResponse): MapModel {
  const target = position.stop;
  const coords: LatLng[] = (shape?.coordinates ?? []).map(([lon, lat]) => [lat, lon]);
  const stops: MapModel['stops'] = [...(shape?.stops ?? [])]
    .sort((a, b) => a.sequence - b.sequence)
    .map((stop) => ({
      id: stop.stop_id,
      name: stop.name,
      latLng: [stop.lat, stop.lon],
      isTarget: stop.stop_id === target.stop_id,
    }));
  const targetLatLng: LatLng = [target.lat, target.lon];
  if (!stops.some((stop) => stop.isTarget)) {
    stops.push({ id: target.stop_id, name: target.name, latLng: targetLatLng, isTarget: true });
  }

  const estimate = position.position;
  const bus: MapModel['bus'] =
    estimate === null
      ? null
      : {
          latLng: [estimate.lat, estimate.lon],
          bearing: estimate.bearing_deg,
          scheduled: position.source === 'SCHEDULED',
        };

  let fitBounds: Bounds;
  if (bus !== null) fitBounds = boundsOf([bus.latLng, targetLatLng]);
  else if (coords.length > 0) fitBounds = boundsOf([...coords, ...stops.map((s) => s.latLng)]);
  else fitBounds = boxAround(targetLatLng, STOP_ONLY_HALF_SIZE_M);

  return {
    line: { coords, color: accessibleLineColors(shape?.color ?? null, MAP_BACKGROUND).bg },
    stops,
    bus,
    fitBounds,
  };
}
