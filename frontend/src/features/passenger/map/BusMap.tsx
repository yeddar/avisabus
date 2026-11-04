import 'leaflet/dist/leaflet.css';
import './busMap.css';

import { control, type Map as LeafletMap, type MapOptions } from 'leaflet';
import { type Ref, useEffect, useId, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  CircleMarker,
  MapContainer,
  Marker,
  Pane,
  Polyline,
  TileLayer,
  Tooltip,
  useMap,
  ZoomControl,
} from 'react-leaflet';

import { busIcon } from './busIcon';
import type { Bounds, MapModel } from './mapModel';
import { FIT_OPTIONS, useInitialFit } from './useInitialFit';

/** Default tiles (passenger_map_view.AC-09); `VITE_MAP_TILE_URL` replaces them. */
export const OSM_TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
const OSM_COPYRIGHT_URL = 'https://www.openstreetmap.org/copyright';

/** Leaflet pane of the route: class `leaflet-route-pane`, under the stops. */
const ROUTE_PANE = 'routePane';
const REDUCED_MOTION = '(prefers-reduced-motion: reduce)';
/** The passenger's stop: larger, with a thick `text` border (docs/design.md §5.7). */
const TARGET_STOP_STYLE = { color: '#14171f', weight: 4, fillColor: '#ffffff', fillOpacity: 1 };

function tileUrl(): string {
  const configured: unknown = import.meta.env.VITE_MAP_TILE_URL;
  return typeof configured === 'string' && configured.trim() !== '' ? configured : OSM_TILE_URL;
}

/**
 * Animations off with prefers-reduced-motion (passenger_map_view.AC-10). Leaflet only reads these
 * options when it creates the map, so the preference is taken once, on mount.
 */
function motionOptions(): MapOptions {
  const reduce =
    typeof window.matchMedia === 'function' && window.matchMedia(REDUCED_MOTION).matches;
  return reduce
    ? { zoomAnimation: false, fadeAnimation: false, markerZoomAnimation: false, inertia: false }
    : {};
}

/** "© colaboradores de OpenStreetMap" with a link, bottom right, in the active language. */
function OsmAttribution() {
  const map = useMap();
  const { t } = useTranslation();
  const text = t('map.osmAttribution');

  useEffect(() => {
    const attribution = control.attribution({ position: 'bottomright', prefix: false });
    const link = document.createElement('a');
    link.href = OSM_COPYRIGHT_URL;
    link.textContent = text;
    attribution.addAttribution(link.outerHTML).addTo(map);
    return () => {
      attribution.remove();
    };
  }, [map, text]);

  return null;
}

/**
 * Keys that do not depend on the position in the list ("508|0", or "508|1" for a stop repeated
 * on a circular line): when the shape arrives the passenger's stop moves in the list, and
 * remounting it would leave an empty "Tu parada" tooltip fading out for 200 ms.
 */
function stableKeys(ids: string[]): string[] {
  const seen = new Map<string, number>();
  return ids.map((id) => {
    const occurrence = seen.get(id) ?? 0;
    seen.set(id, occurrence + 1);
    return `${id}|${occurrence}`;
  });
}

function InitialFit({ bounds, ready }: { bounds: Bounds; ready: boolean }) {
  useInitialFit(useMap(), bounds, ready);
  return null;
}

export interface BusMapProps {
  model: MapModel;
  /**
   * The bounds of `model` are final for the first framing (e.g. the shape has arrived, or there
   * is a position): until then the map is not framed (AC-08).
   */
  ready: boolean;
  ref?: Ref<LeafletMap>;
}

/**
 * Map of the trip (passenger_map_view.AC-07 … AC-11): shape, stops, the passenger's stop with the
 * "Tu parada" label and the bus with its label; no legend; OSM tiles and attribution; keyboard
 * zoom and pan; no focusable markers. Thin Leaflet layer over `MapModel`.
 */
export function BusMap({ model, ready, ref }: BusMapProps) {
  const { t, i18n } = useTranslation();
  const descriptionId = useId();
  const [options] = useState(motionOptions);
  const stopKeys = useMemo(() => stableKeys(model.stops.map((stop) => stop.id)), [model.stops]);
  // Leaflet needs a view from the start; useInitialFit then frames the final bounds once.
  const [initialBounds] = useState(model.fitBounds);
  const color = model.line.color;
  const lineStyle = useMemo(() => ({ color, weight: 5, opacity: 0.9 }), [color]);
  const stopStyle = useMemo(
    () => ({ color, weight: 2, fillColor: '#ffffff', fillOpacity: 1 }),
    [color],
  );
  const busLabel = t(model.bus?.scheduled === true ? 'map.busScheduled' : 'map.busEstimated');
  const icon = useMemo(
    () =>
      model.bus === null
        ? null
        : busIcon({
            bearing: model.bus.bearing,
            scheduled: model.bus.scheduled,
            label: busLabel,
            color: model.line.color,
          }),
    [model.bus, model.line.color, busLabel],
  );

  return (
    <section
      aria-label={t('map.region')}
      aria-describedby={descriptionId}
      className="bus-map h-[360px] overflow-hidden rounded-[14px] border border-control-border"
    >
      <p id={descriptionId} hidden>
        {t('map.regionDescription')}
      </p>
      <MapContainer
        ref={ref}
        className="size-full"
        bounds={initialBounds}
        boundsOptions={FIT_OPTIONS}
        keyboard
        zoomControl={false}
        attributionControl={false}
        {...options}
      >
        <TileLayer url={tileUrl()} />
        <OsmAttribution />
        <ZoomControl
          key={i18n.language}
          position="topright"
          zoomInTitle={t('map.zoomIn')}
          zoomOutTitle={t('map.zoomOut')}
        />
        {/* The route under the stops, whatever arrives first (overlayPane is at z-index 400). */}
        <Pane name={ROUTE_PANE} style={{ zIndex: 390 }}>
          {model.line.coords.length > 0 && (
            <Polyline positions={model.line.coords} pathOptions={lineStyle} interactive={false} />
          )}
        </Pane>
        {model.stops.map((stop, index) => (
          <CircleMarker
            key={stopKeys[index]}
            center={stop.latLng}
            radius={stop.isTarget ? 9 : 5}
            pathOptions={stop.isTarget ? TARGET_STOP_STYLE : stopStyle}
            interactive={false}
          >
            {stop.isTarget && (
              <Tooltip permanent direction="top" offset={[0, -10]} className="map-label">
                {t('map.yourStop')}
              </Tooltip>
            )}
          </CircleMarker>
        ))}
        {model.bus !== null && icon !== null && (
          <Marker
            position={model.bus.latLng}
            icon={icon}
            keyboard={false}
            interactive={false}
            zIndexOffset={1000}
          />
        )}
        <InitialFit bounds={model.fitBounds} ready={ready} />
      </MapContainer>
    </section>
  );
}
