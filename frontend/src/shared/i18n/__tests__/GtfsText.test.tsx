import { act, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { renderWithProviders } from '../../../test/render';
import { GtfsText } from '../GtfsText';

const STOP_NAME = 'Pl. de l’Ajuntament - Mercat Central';

describe('GtfsText', () => {
  afterEach(() => localStorage.clear());

  it('[frontend_i18n.AC-06] shows the GTFS name untranslated and marked as Valencian when the interface is in Spanish', () => {
    renderWithProviders(<GtfsText>{STOP_NAME}</GtfsText>, { language: 'es' });

    const text = screen.getByText(STOP_NAME);
    expect(text.tagName).toBe('SPAN');
    expect(text).toHaveAttribute('lang', 'ca-ES-valencia');
    expect(text.textContent).toBe(STOP_NAME);
  });

  it('[frontend_i18n.AC-06] does not add lang when the interface is already in Valencian', () => {
    renderWithProviders(<GtfsText>{STOP_NAME}</GtfsText>, { language: 'ca' });

    expect(screen.getByText(STOP_NAME)).not.toHaveAttribute('lang');
  });

  it('[frontend_i18n.AC-06] follows language changes', async () => {
    const { i18n } = renderWithProviders(<GtfsText>{STOP_NAME}</GtfsText>, { language: 'ca' });

    await act(async () => {
      await i18n.changeLanguage('es');
    });

    expect(screen.getByText(STOP_NAME)).toHaveAttribute('lang', 'ca-ES-valencia');
  });

  it('[frontend_i18n.AC-06] can render as strong', () => {
    renderWithProviders(<GtfsText as="strong">{STOP_NAME}</GtfsText>, { language: 'es' });

    const text = screen.getByText(STOP_NAME);
    expect(text.tagName).toBe('STRONG');
    expect(text).toHaveAttribute('lang', 'ca-ES-valencia');
  });
});
