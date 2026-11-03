import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { contrastRatio } from '../../../../shared/color/contrast';
import { renderWithProviders } from '../../../../test/render';
import { LineBadge } from '../LineBadge';

function rgbToHex(rgb: string): string {
  const [r, g, b] = (rgb.match(/\d+/g) ?? []).map(Number);
  return `#${[r, g, b].map((c) => (c ?? 0).toString(16).padStart(2, '0')).join('')}`;
}

function colours(element: HTMLElement) {
  return { bg: rgbToHex(element.style.backgroundColor), fg: rgbToHex(element.style.color) };
}

describe('LineBadge', () => {
  it('[passenger_stop_view.AC-11] uses the line colour when it already has enough contrast', () => {
    renderWithProviders(<LineBadge line="7" color="0B3D91" textColor="FFFFFF" />);

    expect(colours(screen.getByText('7'))).toEqual({ bg: '#0b3d91', fg: '#ffffff' });
  });

  it('[passenger_stop_view.AC-11] darkens the EMT red to reach at least 4.5:1 with white', () => {
    renderWithProviders(<LineBadge line="93" color="FE0000" textColor="FFFFFF" />);

    const { bg, fg } = colours(screen.getByText('93'));
    expect(bg).not.toBe('#fe0000');
    expect(contrastRatio(bg, fg)).toBeGreaterThanOrEqual(4.5);
  });

  it('[passenger_stop_view.AC-11] uses a neutral style when the line has no colour', () => {
    renderWithProviders(<LineBadge line="N4" color={null} textColor={null} />);

    expect(colours(screen.getByText('N4'))).toEqual({ bg: '#1f2937', fg: '#ffffff' });
  });

  it('[passenger_stop_view.AC-11] has the sizes of docs/design.md §5.2', () => {
    const { rerender } = renderWithProviders(
      <LineBadge line="93" color="FE0000" textColor="FFFFFF" />,
    );
    expect(screen.getByText('93')).toHaveClass('h-10', 'min-w-[3.25rem]', 'text-[1.375rem]');

    rerender(<LineBadge line="93" color="FE0000" textColor="FFFFFF" size="list" />);
    expect(screen.getByText('93')).toHaveClass('h-9', 'min-w-12', 'text-xl');
  });
});
