import { act, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { renderWithProviders } from '../../../test/render';
import { SkipLink } from '../SkipLink';
import { VisuallyHidden } from '../VisuallyHidden';

describe('SkipLink', () => {
  it.each([
    ['es', 'Saltar al contenido'],
    ['ca', 'Botar al contingut'],
  ] as const)('[frontend_i18n.AC-10] is a translated link to #main (%s)', (language, name) => {
    renderWithProviders(<SkipLink />, { language });

    expect(screen.getByRole('link', { name })).toHaveAttribute('href', '#main');
  });

  it('[frontend_i18n.AC-10] moves the focus to main', () => {
    renderWithProviders(
      <>
        <SkipLink />
        <main id="main" tabIndex={-1}>
          content
        </main>
      </>,
    );

    act(() => screen.getByRole('link').click());

    expect(document.activeElement).toBe(screen.getByRole('main'));
  });

  it('[frontend_i18n.AC-13] is hidden until it receives focus and keeps a 44 px target', () => {
    renderWithProviders(<SkipLink />);

    expect(screen.getByRole('link')).toHaveClass('sr-only', 'focus:not-sr-only', 'min-h-11');
  });
});

describe('VisuallyHidden', () => {
  it('keeps the text for assistive technologies only', () => {
    renderWithProviders(<VisuallyHidden>only for screen readers</VisuallyHidden>);

    expect(screen.getByText('only for screen readers')).toHaveClass('sr-only');
  });
});
