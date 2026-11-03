import { act, fireEvent, screen } from '@testing-library/react';
import { useTranslation } from 'react-i18next';
import { afterEach, describe, expect, it } from 'vitest';

import { renderWithProviders } from '../../../test/render';
import { LanguageSelector } from '../LanguageSelector';
import { LANGUAGE_STORAGE_KEY } from '../languages';

function Probe() {
  const { t } = useTranslation();
  return <p data-testid="probe">{t('layout.skipToContent')}</p>;
}

describe('LanguageSelector', () => {
  afterEach(() => localStorage.clear());

  it.each([
    ['es', 'Idioma'],
    ['ca', 'Llengua'],
  ] as const)(
    '[frontend_i18n.AC-04] has the visible accessible label of %s: %s',
    (language, label) => {
      renderWithProviders(<LanguageSelector />, { language });

      const select = screen.getByRole('combobox', { name: label });
      expect(select.tagName).toBe('SELECT');
      expect(screen.getByText(label).tagName).toBe('LABEL');
    },
  );

  it.each(['es', 'ca'] as const)(
    '[frontend_i18n.AC-04] names each option in its own language and marks its lang (%s interface)',
    (language) => {
      renderWithProviders(<LanguageSelector />, { language });

      const options = screen.getAllByRole('option');
      expect(options.map((o) => o.textContent)).toEqual(['Castellano', 'Valencià']);
      expect(options.map((o) => o.getAttribute('lang'))).toEqual(['es', 'ca-ES-valencia']);
      expect(options.map((o) => o.getAttribute('value'))).toEqual(['es', 'ca']);
    },
  );

  it.each([
    ['es', 'Castellano'],
    ['ca', 'Valencià'],
  ] as const)('[frontend_i18n.AC-04] selects the active language (%s)', (language, name) => {
    renderWithProviders(<LanguageSelector />, { language });

    expect(screen.getByRole('option', { name, selected: true })).toBeInTheDocument();
  });

  it('[frontend_i18n.AC-02] changes every text without reloading and remembers the choice', async () => {
    renderWithProviders(
      <>
        <LanguageSelector />
        <Probe />
      </>,
      { language: 'es' },
    );
    const select = screen.getByRole('combobox', { name: 'Idioma' });
    expect(screen.getByTestId('probe')).toHaveTextContent('Saltar al contenido');

    await act(async () => {
      fireEvent.change(select, { target: { value: 'ca' } });
    });

    expect(screen.getByTestId('probe')).toHaveTextContent('Botar al contingut');
    expect(screen.getByRole('combobox', { name: 'Llengua' })).toHaveValue('ca');
    expect(document.documentElement.lang).toBe('ca-ES-valencia');
    expect(localStorage.getItem(LANGUAGE_STORAGE_KEY)).toBe('ca');
  });

  it('[frontend_i18n.AC-13] keeps a 44 px high control with the design border', () => {
    renderWithProviders(<LanguageSelector />);

    expect(screen.getByRole('combobox')).toHaveClass(
      'min-h-11',
      'border-control-border',
      'rounded-lg',
    );
  });
});
