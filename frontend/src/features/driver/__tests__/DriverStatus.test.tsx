import { fireEvent, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '../../../test/render';
import { DriverStatus } from '../DriverStatus';
import type { DriverView } from '../types';
import { driverView } from './fixtures';

/** The status notices of the view, without the shared announcement region. */
function notices() {
  return screen.queryAllByRole('status').filter((element) => !element.matches('.sr-only'));
}

function notice() {
  expect(notices()).toHaveLength(1);
  return notices()[0] as HTMLElement;
}

function renderStatus(
  view: DriverView | null,
  overrides: Partial<Parameters<typeof DriverStatus>[0]> = {},
) {
  const onRetry = vi.fn();
  const onNextDeparture = vi.fn();
  const result = renderWithProviders(
    <DriverStatus
      view={view}
      permission="granted"
      socketStatus="connected"
      onRetryPermission={onRetry}
      onNextDeparture={onNextDeparture}
      {...overrides}
    />,
  );
  return { onRetry, onNextDeparture, ...result };
}

describe('DriverStatus', () => {
  it('[driver_ui.AC-08] with everything fine it shows nothing', () => {
    renderStatus(driverView());

    expect(notices()).toHaveLength(0);
  });

  it('[driver_ui.AC-08] shows the waiting and stale GPS states with text and icon', () => {
    const { container, rerender } = renderStatus(driverView({ gps: 'WAITING' }));

    expect(notice()).toHaveTextContent('Esperando ubicación…');
    expect(container.querySelector('svg')).toBeInTheDocument();

    rerender(
      <DriverStatus
        view={driverView({ gps: 'STALE' })}
        permission="granted"
        socketStatus="connected"
        onRetryPermission={vi.fn()}
        onNextDeparture={vi.fn()}
      />,
    );

    expect(notice()).toHaveTextContent('Posición desactualizada');
  });

  it('[driver_ui.AC-08] shows that the bus is off the route of the line', () => {
    renderStatus(driverView({ off_route: true }));

    expect(notice()).toHaveTextContent('No estás en el recorrido de esta línea');
  });

  it('[driver_ui.AC-08] shows that there is no connection with the server, even without a view', () => {
    renderStatus(null, { socketStatus: 'disconnected' });

    expect(notice()).toHaveTextContent('Sin conexión, reconectando…');
  });

  it('[driver_ui.AC-08] does not show the connection state while it is still connecting', () => {
    renderStatus(null, { socketStatus: 'connecting' });

    expect(notices()).toHaveLength(0);
  });

  it('[driver_ui.AC-04] with the location permission denied it explains it and offers "Reintentar"', () => {
    const { onRetry } = renderStatus(driverView({ gps: 'WAITING' }), { permission: 'denied' });

    expect(notice()).toHaveTextContent(
      'Sin permiso de ubicación: no se pueden calcular las próximas paradas',
    );
    expect(screen.queryByText('Esperando ubicación…')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Reintentar' }));

    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('[driver_ui.AC-08] at the end of the route offers the next departure', () => {
    const { onNextDeparture } = renderStatus(driverView({ finished: true }));

    expect(notice()).toHaveTextContent('Fin del recorrido');

    fireEvent.click(screen.getByRole('button', { name: 'Elegir la siguiente salida' }));

    expect(onNextDeparture).toHaveBeenCalledTimes(1);
  });
});
