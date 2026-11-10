import { fireEvent, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '../../../test/render';
import { EndShiftDialog } from '../EndShiftDialog';

describe('EndShiftDialog', () => {
  it('[driver_ui.AC-10] asks for confirmation with "Finalizar" and "Seguir"', () => {
    renderWithProviders(<EndShiftDialog onConfirm={vi.fn()} onCancel={vi.fn()} />);

    const dialog = screen.getByRole('dialog', { name: '¿Finalizar el turno?' });
    expect(dialog).toHaveAttribute('open');
    expect(screen.getByRole('button', { name: 'Finalizar' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Seguir' })).toBeInTheDocument();
  });

  it('[driver_ui.AC-10] "Finalizar" confirms and "Seguir" cancels', () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    renderWithProviders(<EndShiftDialog onConfirm={onConfirm} onCancel={onCancel} />);

    fireEvent.click(screen.getByRole('button', { name: 'Seguir' }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    expect(onConfirm).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Finalizar' }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });
});
