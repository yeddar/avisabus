import { act, fireEvent, screen, within } from '@testing-library/react';
import { type Map as LeafletMap, point, type TileLayer } from 'leaflet';
import { createRef } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { Language } from '../../../../shared/i18n/languages';
import {
  POSITION_EN_ROUTE,
  POSITION_NO_ARRIVAL,
  POSITION_NOT_STARTED,
  SHAPE_93,
} from '../../../../test/fixtures/api';
import { renderWithProviders } from '../../../../test/render';
import { BusMap, OSM_TILE_URL } from '../BusMap';
import { buildMapModel } from '../mapModel';

const DESCRIPTION =
  'La misma información está en texto en el resumen «Dónde está el autobús», antes del mapa.';

function setReducedMotion(reduce: boolean) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn((query: string) => ({
      matches: reduce && query === '(prefers-reduced-motion: reduce)',
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
}

function renderMap({
  position = POSITION_EN_ROUTE(),
  shape = SHAPE_93() as ReturnType<typeof SHAPE_93> | null,
  language = 'es' as Language,
} = {}) {
  const ref = createRef<LeafletMap>();
  const view = renderWithProviders(
    <BusMap ref={ref} model={buildMapModel(shape, position)} ready />,
    { language },
  );
  const map = () => {
    if (ref.current === null) throw new Error('map not created');
    return ref.current;
  };
  return { ...view, map, region: screen.getByRole('region', { name: /recorr/ }) };
}

function tileLayer(map: LeafletMap): TileLayer {
  let found: TileLayer | null = null;
  map.eachLayer((layer) => {
    if ('getTileUrl' in layer) found = layer as TileLayer;
  });
  if (found === null) throw new Error('no tile layer');
  return found;
}

/**
 * Presses an arrow key on the focused map, as a keyboard user. jsdom lays nothing out, so the map
 * is given a real size: otherwise Leaflet never animates a pan (it jumps when the offset does not
 * fit in a 0 × 0 map).
 */
function pressArrowRight(map: LeafletMap) {
  map.getSize = () => point(400, 360);
  act(() => map.getContainer().focus());
  act(() => {
    fireEvent.keyDown(document, { key: 'ArrowRight', keyCode: 39 });
  });
  return map.getPane('mapPane')!;
}

describe('BusMap', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it('[passenger_map_view.AC-11] is a region "Mapa del recorrido" described as an alternative to the summary', () => {
    const { region } = renderMap();

    expect(region).toHaveAccessibleName('Mapa del recorrido');
    expect(region).toHaveAccessibleDescription(DESCRIPTION);
    expect(region.querySelector('.leaflet-container')).not.toBeNull();
  });

  it('[passenger_map_view.AC-11] in Valencian', () => {
    renderMap({ language: 'ca' });

    expect(screen.getByRole('region', { name: 'Mapa del recorregut' })).toHaveAccessibleDescription(
      "La mateixa informació està en text en el resum «On està l'autobús», abans del mapa.",
    );
  });

  it('[passenger_map_view.AC-07] draws the shape in the line colour, the stops and the bus', () => {
    const shape = SHAPE_93();
    const { region } = renderMap({ shape });

    const route = [...region.querySelectorAll('.leaflet-route-pane path')];
    expect(route).toHaveLength(1);
    expect(route[0]).toHaveAttribute('stroke', '#e50000');
    // One circle per stop, in a pane above the route.
    expect(region.querySelectorAll('.leaflet-overlay-pane path')).toHaveLength(shape.stops.length);
    const zIndex = (selector: string) =>
      Number(region.querySelector<HTMLElement>(selector)?.style.zIndex || 400);
    expect(zIndex('.leaflet-route-pane')).toBeLessThan(zIndex('.leaflet-overlay-pane'));
    const bus = region.querySelector('.leaflet-marker-pane [data-bus-arrow]');
    expect(bus?.getAttribute('style')).toContain('rotate(100.94859961754514deg)');
  });

  it("[passenger_map_view.AC-05] [passenger_map_view.AC-07] labels the passenger's stop and the bus with visible text, without a legend", () => {
    const { region } = renderMap();

    expect(within(region).getByText('Tu parada')).toBeVisible();
    expect(within(region).getByText('Estimada')).toBeVisible();
    expect(region.querySelector('.leaflet-control-layers, .legend')).toBeNull();
  });

  it('[passenger_map_view.AC-05] labels a scheduled bus "Según horario" / "Segons horari"', () => {
    const { region } = renderMap({ position: POSITION_NOT_STARTED() });
    expect(within(region).getByText('Según horario')).toBeInTheDocument();
  });

  it('[passenger_map_view.AC-05] in Valencian: "La teua parada" and "Estimada"', () => {
    const { region } = renderMap({ language: 'ca' });

    expect(within(region).getByText('La teua parada')).toBeInTheDocument();
    expect(within(region).getByText('Estimada')).toBeInTheDocument();
  });

  it('[passenger_map_view.AC-07] without a position draws only the shape and the stops', () => {
    const shape = SHAPE_93();
    const { region } = renderMap({ position: POSITION_NO_ARRIVAL(), shape });

    expect(region.querySelectorAll('.leaflet-route-pane path')).toHaveLength(1);
    expect(region.querySelectorAll('.leaflet-overlay-pane path')).toHaveLength(shape.stops.length);
    expect(region.querySelector('.leaflet-marker-pane')?.children).toHaveLength(0);
  });

  it('[passenger_map_view.AC-07] without a shape draws the passenger stop and the bus', () => {
    const { region } = renderMap({ shape: null });

    const circles = [...region.querySelectorAll('.leaflet-overlay-pane path')].filter(
      (path) => path.getAttribute('fill') === '#ffffff',
    );
    expect(circles).toHaveLength(1);
    expect(within(region).getByText('Tu parada')).toBeInTheDocument();
    expect(within(region).getByText('Estimada')).toBeInTheDocument();
  });

  it('[passenger_map_view.AC-07] no marker can take the keyboard focus', () => {
    const { region } = renderMap();

    const focusable = region.querySelectorAll(
      '.leaflet-marker-pane [tabindex], .leaflet-overlay-pane [tabindex]',
    );
    expect(focusable).toHaveLength(0);
  });

  it('[passenger_map_view.AC-09] shows the OpenStreetMap attribution with a link to its licence', () => {
    const { region } = renderMap();

    const link = within(region).getByRole('link', { name: '© colaboradores de OpenStreetMap' });
    expect(link).toHaveAttribute('href', 'https://www.openstreetmap.org/copyright');
    expect(link.closest('.leaflet-control-attribution')).not.toBeNull();
    expect(link.closest('.leaflet-bottom.leaflet-right')).not.toBeNull();
  });

  it('[passenger_map_view.AC-09] uses the OSM tiles by default and VITE_MAP_TILE_URL when set', () => {
    expect(OSM_TILE_URL).toBe('https://tile.openstreetmap.org/{z}/{x}/{y}.png');
    const osm = renderMap();
    // The zoom of the URL is the map's.
    expect(tileLayer(osm.map()).getTileUrl({ x: 1, y: 2, z: 3 } as never)).toMatch(
      /^https:\/\/tile\.openstreetmap\.org\/\d+\/1\/2\.png$/,
    );
    osm.unmount();

    vi.stubEnv('VITE_MAP_TILE_URL', 'https://tiles.example.test/{z}/{x}/{y}.png');
    const custom = renderMap();
    expect(tileLayer(custom.map()).getTileUrl({ x: 1, y: 2, z: 3 } as never)).toMatch(
      /^https:\/\/tiles\.example\.test\/\d+\/1\/2\.png$/,
    );
  });

  it('[passenger_map_view.AC-09] zoom buttons are labelled in the active language, top right', async () => {
    const { region, i18n } = renderMap();

    const zoomIn = within(region).getByRole('button', { name: 'Acercar' });
    expect(within(region).getByRole('button', { name: 'Alejar' })).toBeInTheDocument();
    expect(zoomIn.closest('.leaflet-top.leaflet-right')).not.toBeNull();

    await act(async () => {
      await i18n.changeLanguage('ca');
    });
    expect(within(region).getByRole('button', { name: 'Acosta' })).toBeInTheDocument();
    expect(within(region).getByRole('button', { name: 'Allunya' })).toBeInTheDocument();
    expect(within(region).queryByRole('button', { name: 'Acercar' })).toBeNull();
    expect(
      within(region).getByRole('link', { name: "© col·laboradors d'OpenStreetMap" }),
    ).toBeInTheDocument();
    expect(within(region).queryByText('© colaboradores de OpenStreetMap')).toBeNull();
  });

  it('[passenger_map_view.AC-09] the map takes the keyboard focus and pans with the arrows', () => {
    const { map } = renderMap();

    expect(map().options.keyboard).toBe(true);
    expect(map().getContainer().tabIndex).toBe(0);
  });

  it('[passenger_map_view.AC-10] disables zoom, pan and marker animations with prefers-reduced-motion', () => {
    setReducedMotion(true);
    const { map } = renderMap();

    expect(map().options).toMatchObject({
      zoomAnimation: false,
      fadeAnimation: false,
      markerZoomAnimation: false,
      inertia: false,
    });
  });

  it('[passenger_map_view.AC-10] keeps the animations without the preference', () => {
    setReducedMotion(false);
    const { map } = renderMap();

    expect(map().options).toMatchObject({
      fadeAnimation: true,
      markerZoomAnimation: true,
      inertia: true,
    });
  });

  it('[passenger_map_view.AC-10] with prefers-reduced-motion the arrow keys pan the map at once, without animation', () => {
    setReducedMotion(true);
    const { map } = renderMap();
    const before = map().getCenter();

    const pane = pressArrowRight(map());

    expect(pane).not.toHaveClass('leaflet-pan-anim');
    expect(map().getCenter().lng).toBeGreaterThan(before.lng); // already moved, no frames
  });

  it('[passenger_map_view.AC-10] with prefers-reduced-motion programmatic pans are not animated either', () => {
    setReducedMotion(true);
    const { map } = renderMap();
    map().getSize = () => point(400, 360);

    act(() => {
      map().panBy([50, 0]);
      map().panTo(map().containerPointToLatLng([260, 180]));
    });

    expect(map().getPane('mapPane')).not.toHaveClass('leaflet-pan-anim');
  });

  it("[passenger_map_view.AC-10] without the preference the arrow keys keep Leaflet's pan animation", () => {
    setReducedMotion(false);
    const { map } = renderMap();

    expect(pressArrowRight(map())).toHaveClass('leaflet-pan-anim');
  });
});
