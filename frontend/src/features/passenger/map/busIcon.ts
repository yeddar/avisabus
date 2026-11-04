import { type DivIcon, divIcon } from 'leaflet';

export interface BusIconOptions {
  /** Bearing of the shape segment, 0–360° (null: no arrow). */
  bearing: number | null;
  /** Position from the timetable: dashed border (design §3). */
  scheduled: boolean;
  /** Visible label, "Estimada" or "Según horario" (passenger_map_view.AC-05). */
  label: string;
  /** Accessible line colour (white text on it is ≥ 4.5:1). */
  color: string;
}

/** Size of the whole marker (disc, arrow ring and label) and the point anchored to the bus. */
const SIZE: [number, number] = [120, 74];
const ANCHOR: [number, number] = [60, 24];

const ESCAPES: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
};

function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (char) => ESCAPES[char] ?? char);
}

/** Bus pictogram of docs/design.md §6 (same strokes as shared/ui/icons/BusIcon). */
const BUS_SVG =
  '<svg aria-hidden="true" focusable="false" viewBox="0 0 24 24" width="22" height="22" ' +
  'fill="none" stroke="#ffffff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">' +
  '<rect x="4" y="3" width="16" height="15" rx="3"/><path d="M4 11h16"/><path d="M8 7h8"/>' +
  '<path d="M7 18v2.5"/><path d="M17 18v2.5"/></svg>';

/** Arrow on a 48 px ring around the disc, pointing north before the rotation. */
const arrowSvg = (bearing: number) =>
  `<svg data-bus-arrow aria-hidden="true" focusable="false" class="bus-marker__arrow" ` +
  `viewBox="0 0 48 48" width="48" height="48" style="transform: rotate(${bearing}deg)">` +
  '<path d="M24 0 L31 9 L17 9 Z" fill="#14171f" stroke="#ffffff" stroke-width="1.5"/></svg>';

/**
 * Leaflet icon of the bus (passenger_map_view.AC-05, AC-07): a disc in the line colour with
 * the bus pictogram, an arrow rotated by `bearing_deg` and the visible label under it, on the
 * `text` colour with white 13 px letters (docs/design.md §5.7). The drawings are decorative; the
 * label is plain text.
 */
export function busIcon({ bearing, scheduled, label, color }: BusIconOptions): DivIcon {
  const html =
    `<div class="bus-marker${scheduled ? ' bus-marker--scheduled' : ''}">` +
    '<div class="bus-marker__icon">' +
    (bearing === null ? '' : arrowSvg(bearing)) +
    `<span data-bus-disc class="bus-marker__disc" style="background-color: ${color}">${BUS_SVG}</span>` +
    '</div>' +
    `<span data-bus-label class="bus-marker__label">${escapeHtml(label)}</span>` +
    '</div>';
  return divIcon({ html, className: 'bus-marker-root', iconSize: SIZE, iconAnchor: ANCHOR });
}
