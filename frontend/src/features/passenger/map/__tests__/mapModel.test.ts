import { describe, expect, it } from 'vitest';

import { contrastRatio } from '../../../../shared/color/contrast';
import {
  POSITION_EN_ROUTE,
  POSITION_NO_ARRIVAL,
  POSITION_NOT_STARTED,
  SHAPE_93,
} from '../../../../test/fixtures/api';
import { buildMapModel, STOP_ONLY_HALF_SIZE_M } from '../mapModel';

const METERS_PER_DEGREE_LAT = 111_320;

describe('buildMapModel', () => {
  it('[passenger_map_view.AC-07] draws the shape as [lat, lon] in the accessible line colour', () => {
    const shape = SHAPE_93();
    const model = buildMapModel(shape, POSITION_EN_ROUTE());

    expect(model.line.coords).toHaveLength(shape.coordinates.length);
    expect(model.line.coords[0]).toEqual([shape.coordinates[0]![1], shape.coordinates[0]![0]]);
    // EMT red FE0000 is darkened like the line badges: 4.5:1 on white.
    expect(model.line.color).toBe('#e50000');
    expect(contrastRatio(model.line.color, '#ffffff')).toBeGreaterThanOrEqual(4.5);
  });

  it('[passenger_map_view.AC-07] uses the neutral colour when the line has none', () => {
    const model = buildMapModel({ ...SHAPE_93(), color: null }, POSITION_EN_ROUTE());

    expect(model.line.color).toBe('#1f2937');
  });

  it("[passenger_map_view.AC-07] lists the shape's stops in order and highlights the passenger's", () => {
    const shape = SHAPE_93();
    const model = buildMapModel(shape, POSITION_EN_ROUTE());

    expect(model.stops.map((stop) => stop.id)).toEqual(shape.stops.map((stop) => stop.stop_id));
    expect(model.stops.filter((stop) => stop.isTarget).map((stop) => stop.id)).toEqual(['508']);
    const first = shape.stops[0]!;
    expect(model.stops[0]).toEqual({
      id: first.stop_id,
      name: first.name,
      latLng: [first.lat, first.lon],
      isTarget: false,
    });
  });

  it('[passenger_map_view.AC-07] adds the passenger stop from the position when the shape does not list it', () => {
    const shape = SHAPE_93();
    shape.stops = shape.stops.filter((stop) => stop.stop_id !== '508');
    const position = POSITION_EN_ROUTE();

    const model = buildMapModel(shape, position);

    expect(model.stops.filter((stop) => stop.isTarget)).toEqual([
      {
        id: '508',
        name: "Parc de l'Oest - Enguera",
        latLng: [position.stop.lat, position.stop.lon],
        isTarget: true,
      },
    ]);
  });

  it('[passenger_map_view.AC-07] places the bus with its bearing, marked as scheduled or not', () => {
    const position = POSITION_EN_ROUTE();
    expect(buildMapModel(SHAPE_93(), position).bus).toEqual({
      latLng: [position.position!.lat, position.position!.lon],
      bearing: position.position!.bearing_deg,
      scheduled: false,
    });

    expect(buildMapModel(SHAPE_93(), POSITION_NOT_STARTED()).bus?.scheduled).toBe(true);
  });

  it('[passenger_map_view.AC-07] [passenger_map_view.AC-08] without a position: only the shape and stops, framing the whole shape', () => {
    const shape = SHAPE_93();
    const model = buildMapModel(shape, POSITION_NO_ARRIVAL());

    expect(model.bus).toBeNull();
    expect(model.line.coords).toHaveLength(shape.coordinates.length);
    const lats = [...shape.coordinates.map(([, lat]) => lat), ...shape.stops.map((s) => s.lat)];
    const lons = [...shape.coordinates.map(([lon]) => lon), ...shape.stops.map((s) => s.lon)];
    expect(model.fitBounds).toEqual([
      [Math.min(...lats), Math.min(...lons)],
      [Math.max(...lats), Math.max(...lons)],
    ]);
  });

  it('[passenger_map_view.AC-08] with a position: frames the bus and the passenger stop', () => {
    const position = POSITION_EN_ROUTE();
    const bus = position.position!;
    const stop = position.stop;

    expect(buildMapModel(SHAPE_93(), position).fitBounds).toEqual([
      [Math.min(bus.lat, stop.lat), Math.min(bus.lon, stop.lon)],
      [Math.max(bus.lat, stop.lat), Math.max(bus.lon, stop.lon)],
    ]);
  });

  it('[passenger_map_view.AC-07] [passenger_map_view.AC-08] without a shape: the passenger stop and the bus, framing both', () => {
    const position = POSITION_EN_ROUTE();
    const model = buildMapModel(null, position);

    expect(model.line.coords).toEqual([]);
    expect(model.stops).toEqual([
      {
        id: '508',
        name: "Parc de l'Oest - Enguera",
        latLng: [position.stop.lat, position.stop.lon],
        isTarget: true,
      },
    ]);
    expect(model.bus).not.toBeNull();
    expect(model.fitBounds).toEqual(buildMapModel(SHAPE_93(), position).fitBounds);
  });

  it('[passenger_map_view.AC-07] [passenger_map_view.AC-08] without a shape nor a position: a fixed box around the stop', () => {
    const position = POSITION_NO_ARRIVAL();
    const model = buildMapModel(null, position);

    expect(model.bus).toBeNull();
    expect(model.stops).toHaveLength(1);
    const [[south, west], [north, east]] = model.fitBounds;
    expect((north - south) * METERS_PER_DEGREE_LAT).toBeCloseTo(2 * STOP_ONLY_HALF_SIZE_M, 0);
    expect((north + south) / 2).toBeCloseTo(position.stop.lat, 9);
    expect((east + west) / 2).toBeCloseTo(position.stop.lon, 9);
    expect(east - west).toBeGreaterThan(north - south); // a degree of longitude is shorter
  });
});
