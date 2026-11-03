import { describe, expect, it } from 'vitest';

import { NEUTRAL_LINE_COLORS, accessibleLineColors, contrastRatio } from '../contrast';

describe('contrastRatio', () => {
  it.each([
    ['#000000', '#ffffff', 21],
    ['#ffffff', '#ffffff', 1],
    ['#14171F', '#FFFFFF', 17.9],
    ['#4B5563', '#FFFFFF', 7.6],
    ['#0B3D91', '#FFFFFF', 10.0],
    ['#FE0000', '#FFFFFF', 4.0],
  ])('[passenger_stop_view.AC-11] %s on %s is %d:1 (WCAG 2.x)', (a, b, expected) => {
    expect(contrastRatio(a, b)).toBeCloseTo(expected, 1);
  });

  it('[passenger_stop_view.AC-11] is symmetric and accepts GTFS colours without #', () => {
    expect(contrastRatio('FE0000', 'FFFFFF')).toBeCloseTo(contrastRatio('#ffffff', '#fe0000'), 6);
  });
});

describe('accessibleLineColors', () => {
  it('[passenger_stop_view.AC-11] keeps a line colour that already reaches 4.5:1', () => {
    expect(accessibleLineColors('0B3D91', 'FFFFFF')).toEqual({ bg: '#0b3d91', fg: '#ffffff' });
  });

  it('[passenger_stop_view.AC-11] darkens the EMT red until white text reaches 4.5:1', () => {
    const { bg, fg } = accessibleLineColors('FE0000', 'FFFFFF');

    expect(fg).toBe('#ffffff');
    // One 5-point step (L 49.8 % → 44.8 %): "around #E40000, 4.9:1" in docs/design.md §4.
    expect(bg).toBe('#e50000');
    expect(contrastRatio(bg, fg)).toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio(bg, fg)).toBeCloseTo(4.8, 1);
  });

  it.each([
    ['FF8800', 'FFFFFF'],
    ['33CC33', 'FFFFFF'],
    ['00AEEF', 'FFFFFF'],
    ['FFFF00', 'FFFFFF'],
  ])(
    '[passenger_stop_view.AC-11] darkens %s under %s in 5 %% lightness steps to at least 4.5:1',
    (bg, fg) => {
      const result = accessibleLineColors(bg, fg);

      expect(contrastRatio(result.bg, result.fg)).toBeGreaterThanOrEqual(4.5);
      expect(result.fg).toBe('#ffffff');
      expect(result.bg).not.toBe(`#${bg.toLowerCase()}`);
    },
  );

  it('[passenger_stop_view.AC-11] falls back to black and white when darkening cannot help', () => {
    // Dark text on a mid grey: darkening the background only lowers the contrast.
    expect(accessibleLineColors('555555', '000000')).toEqual({ bg: '#000000', fg: '#ffffff' });
  });

  it.each([
    [null, null],
    [null, 'FFFFFF'],
    ['FE0000', null],
    ['', ''],
    ['not-a-colour', 'FFFFFF'],
  ])(
    '[passenger_stop_view.AC-11] uses the neutral style when the line has no colour (%s, %s)',
    (bg, fg) => {
      expect(accessibleLineColors(bg, fg)).toEqual(NEUTRAL_LINE_COLORS);
      expect(NEUTRAL_LINE_COLORS).toEqual({ bg: '#1f2937', fg: '#ffffff' });
    },
  );
});
