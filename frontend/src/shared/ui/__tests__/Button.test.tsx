import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { Button } from '../Button';
import { LinkButton } from '../LinkButton';

// Tailwind classes that give the 44 × 44 px touch target and docs/design.md §5.5 appearance.
const TOUCH_TARGET = ['min-h-11', 'min-w-11', 'px-4'];
const SHAPE = ['rounded-[10px]', 'border-2', 'border-accent', 'font-bold'];
const PRIMARY = ['bg-accent', 'text-white'];
const SECONDARY = ['bg-surface', 'text-accent'];

describe('Button', () => {
  it('[frontend_i18n.AC-13] has a 44 × 44 px minimum touch target', () => {
    render(<Button>Ok</Button>);

    expect(screen.getByRole('button', { name: 'Ok' })).toHaveClass(...TOUCH_TARGET);
  });

  it('[frontend_i18n.AC-17] primary variant: accent background, white bold text, 2 px border, 10 px radius', () => {
    render(<Button variant="primary">Ok</Button>);

    const button = screen.getByRole('button', { name: 'Ok' });
    expect(button).toHaveClass(...SHAPE, ...PRIMARY);
    expect(button).not.toHaveClass(...SECONDARY);
  });

  it('[frontend_i18n.AC-17] secondary variant (default): white background, accent bold text and border', () => {
    render(<Button>Ok</Button>);

    const button = screen.getByRole('button', { name: 'Ok' });
    expect(button).toHaveClass(...SHAPE, ...SECONDARY);
    expect(button).not.toHaveClass(...PRIMARY);
  });

  it('defaults to type="button" and forwards props', () => {
    let clicks = 0;
    render(
      <Button onClick={() => (clicks += 1)} className="w-full">
        Ok
      </Button>,
    );

    const button = screen.getByRole('button', { name: 'Ok' });
    button.click();
    expect(button).toHaveAttribute('type', 'button');
    expect(button).toHaveClass('w-full');
    expect(clicks).toBe(1);
  });

  it('renders a decorative icon before the always-visible text', () => {
    render(<Button icon={<svg data-testid="icon" />}>Ok</Button>);

    const icon = screen.getByTestId('icon').parentElement;
    expect(icon).toHaveAttribute('aria-hidden', 'true');
    expect(screen.getByRole('button', { name: 'Ok' })).toBeVisible();
  });
});

describe('LinkButton', () => {
  it('[frontend_i18n.AC-13] is a link with a 44 × 44 px minimum touch target', () => {
    render(
      <MemoryRouter>
        <LinkButton to="/map">Map</LinkButton>
      </MemoryRouter>,
    );

    const link = screen.getByRole('link', { name: 'Map' });
    expect(link).toHaveAttribute('href', '/map');
    expect(link).toHaveClass(...TOUCH_TARGET, ...SHAPE, ...SECONDARY);
  });

  it('[frontend_i18n.AC-17] supports the primary variant', () => {
    render(
      <MemoryRouter>
        <LinkButton to="/map" variant="primary">
          Map
        </LinkButton>
      </MemoryRouter>,
    );

    expect(screen.getByRole('link', { name: 'Map' })).toHaveClass(...PRIMARY);
  });
});
