/** WCAG 2.x contrast and accessible line colours (passenger_stop_view.AC-11, design §3). */

export const MIN_TEXT_CONTRAST = 4.5;
export const NEUTRAL_LINE_COLORS = { bg: '#1f2937', fg: '#ffffff' } as const;
const FALLBACK_LINE_COLORS = { bg: '#000000', fg: '#ffffff' } as const;
const LIGHTNESS_STEP = 0.05;
const MAX_STEPS = 20;

type Rgb = readonly [number, number, number];
type Hsl = readonly [number, number, number];

const HEX = /^#?([0-9a-f]{6})$/i;

/** '#rrggbb' or GTFS 'RRGGBB' → [r, g, b] in 0–255; null if it is not a 6-digit colour. */
function parseHex(hex: string): Rgb | null {
  const match = HEX.exec(hex.trim());
  if (match?.[1] === undefined) return null;
  const value = parseInt(match[1], 16);
  return [(value >> 16) & 0xff, (value >> 8) & 0xff, value & 0xff];
}

function toHex([r, g, b]: Rgb): string {
  return `#${[r, g, b].map((c) => Math.round(c).toString(16).padStart(2, '0')).join('')}`;
}

function relativeLuminance([r, g, b]: Rgb): number {
  const [lr, lg, lb] = [r, g, b].map((c) => {
    const s = c / 255;
    return s <= 0.04045 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  }) as [number, number, number];
  return 0.2126 * lr + 0.7152 * lg + 0.0722 * lb;
}

function ratio(a: Rgb, b: Rgb): number {
  const [hi, lo] = [relativeLuminance(a), relativeLuminance(b)].sort((x, y) => y - x) as [
    number,
    number,
  ];
  return (hi + 0.05) / (lo + 0.05);
}

/** WCAG 2.x contrast ratio between two colours ('#rrggbb' or 'RRGGBB'), from 1 to 21. */
export function contrastRatio(hexA: string, hexB: string): number {
  const a = parseHex(hexA);
  const b = parseHex(hexB);
  if (a === null || b === null) throw new Error('contrastRatio expects 6-digit hex colours');
  return ratio(a, b);
}

function rgbToHsl([r, g, b]: Rgb): Hsl {
  const [rn, gn, bn] = [r / 255, g / 255, b / 255];
  const max = Math.max(rn, gn, bn);
  const min = Math.min(rn, gn, bn);
  const l = (max + min) / 2;
  if (max === min) return [0, 0, l];
  const d = max - min;
  const s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
  let h: number;
  if (max === rn) h = (gn - bn) / d + (gn < bn ? 6 : 0);
  else if (max === gn) h = (bn - rn) / d + 2;
  else h = (rn - gn) / d + 4;
  return [h / 6, s, l];
}

function hslToRgb([h, s, l]: Hsl): Rgb {
  if (s === 0) return [l * 255, l * 255, l * 255];
  const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
  const p = 2 * l - q;
  const channel = (t0: number) => {
    const t = t0 < 0 ? t0 + 1 : t0 > 1 ? t0 - 1 : t0;
    if (t < 1 / 6) return p + (q - p) * 6 * t;
    if (t < 1 / 2) return q;
    if (t < 2 / 3) return p + (q - p) * (2 / 3 - t) * 6;
    return p;
  };
  return [channel(h + 1 / 3) * 255, channel(h) * 255, channel(h - 1 / 3) * 255];
}

/**
 * Colours of a line badge: the GTFS line colours if their contrast is at least 4.5:1; otherwise
 * the background is darkened in steps of 5 points of HSL lightness until it is (at most 20
 * steps, then black and white). Lines without a (valid) colour use a neutral style.
 */
export function accessibleLineColors(
  bg: string | null,
  fg: string | null,
): { bg: string; fg: string } {
  const background = bg === null ? null : parseHex(bg);
  const text = fg === null ? null : parseHex(fg);
  if (background === null || text === null) return { ...NEUTRAL_LINE_COLORS };

  const fgHex = toHex(text);
  const [h, s, l] = rgbToHsl(background);
  for (let step = 0; step <= MAX_STEPS; step += 1) {
    const candidate = toHex(hslToRgb([h, s, Math.max(0, l - step * LIGHTNESS_STEP)]));
    const parsed = parseHex(candidate) as Rgb;
    if (ratio(parsed, text) >= MIN_TEXT_CONTRAST) return { bg: candidate, fg: fgHex };
  }
  return { ...FALLBACK_LINE_COLORS };
}
