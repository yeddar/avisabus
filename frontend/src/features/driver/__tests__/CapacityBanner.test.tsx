import { screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { renderWithProviders } from '../../../test/render';
import { CapacityBanner } from '../CapacityBanner';
import { driverView, stopDemand } from './fixtures';

const seatStops = [
  stopDemand({ waiting: 5, needs: { RAMP: 0, EXTRA_TIME: 0, SEAT: 5, VISUAL: 0 } }),
];

describe('CapacityBanner', () => {
  it('[driver_ui.AC-06] without alerts it shows nothing and announces nothing', () => {
    renderWithProviders(<CapacityBanner view={driverView()} />);

    expect(screen.queryByText(/Esperan/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Piden asiento/)).not.toBeInTheDocument();
  });

  it('[driver_ui.AC-06] shows the capacity strip with text and icon, and announces it in role="alert"', async () => {
    const view = driverView({ capacity_alert: true, total_waiting: 35, free_places: 30 });
    const { container } = renderWithProviders(<CapacityBanner view={view} />);

    const strip = screen.getByText('Esperan 35 personas y quedan 30 plazas');
    expect(strip).toBeVisible();
    expect(container.querySelector('svg')).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByRole('alert')).toHaveTextContent('Esperan 35 personas y quedan 30 plazas'),
    );
  });

  it('[driver_ui.AC-06] shows the seats strip counting the requests for a seat', async () => {
    const view = driverView({ seat_alert: true, free_seats: 2, stops: seatStops });
    renderWithProviders(<CapacityBanner view={view} />);

    expect(screen.getByText('Piden asiento 5 personas y quedan 2 asientos')).toBeVisible();
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Piden asiento 5'));
  });

  it('[driver_ui.AC-06] two strips that appear together are announced together, once', async () => {
    const view = driverView({
      capacity_alert: true,
      seat_alert: true,
      total_waiting: 35,
      free_places: 30,
      free_seats: 2,
      stops: seatStops,
    });
    renderWithProviders(<CapacityBanner view={view} />);

    await waitFor(() => {
      const alert = screen.getByRole('alert');
      expect(alert).toHaveTextContent('Esperan 35 personas y quedan 30 plazas');
      expect(alert).toHaveTextContent('Piden asiento 5 personas y quedan 2 asientos');
    });
  });

  it('[driver_ui.AC-06] a strip that stays is not announced again when its numbers change', async () => {
    const first = driverView({ capacity_alert: true, total_waiting: 35, free_places: 30 });
    const { rerender } = renderWithProviders(<CapacityBanner view={first} />);
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Esperan 35'));

    rerender(
      <CapacityBanner
        view={driverView({ capacity_alert: true, total_waiting: 36, free_places: 30 })}
      />,
    );

    expect(screen.getByText('Esperan 36 personas y quedan 30 plazas')).toBeVisible();
    await new Promise((resolve) => setTimeout(resolve, 60));
    expect(screen.getByRole('alert')).toHaveTextContent('Esperan 35');
  });

  it('[driver_ui.AC-06] a strip that disappears and comes back is announced again', async () => {
    const on = driverView({ capacity_alert: true, total_waiting: 35, free_places: 30 });
    const { rerender } = renderWithProviders(<CapacityBanner view={on} />);
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Esperan 35'));

    rerender(<CapacityBanner view={driverView()} />);
    rerender(
      <CapacityBanner
        view={driverView({ capacity_alert: true, total_waiting: 40, free_places: 30 })}
      />,
    );

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Esperan 40'));
  });

  it('[driver_ui.AC-06] the capacity strip uses the singular and the plural correctly (v1.2)', () => {
    const { rerender } = renderWithProviders(
      <CapacityBanner
        view={driverView({ capacity_alert: true, total_waiting: 1, free_places: 0 })}
      />,
    );
    expect(screen.getByText('Espera 1 persona y quedan 0 plazas')).toBeVisible();

    rerender(
      <CapacityBanner
        view={driverView({ capacity_alert: true, total_waiting: 2, free_places: 1 })}
      />,
    );
    expect(screen.getByText('Esperan 2 personas y queda 1 plaza')).toBeVisible();
  });

  it('[driver_ui.AC-06] the seats strip uses the singular and the plural correctly (v1.2)', () => {
    const oneRequest = [
      stopDemand({ waiting: 1, needs: { RAMP: 0, EXTRA_TIME: 0, SEAT: 1, VISUAL: 0 } }),
    ];
    const { rerender } = renderWithProviders(
      <CapacityBanner view={driverView({ seat_alert: true, free_seats: 0, stops: oneRequest })} />,
    );
    expect(screen.getByText('Pide asiento 1 persona y quedan 0 asientos')).toBeVisible();

    rerender(
      <CapacityBanner view={driverView({ seat_alert: true, free_seats: 1, stops: seatStops })} />,
    );
    expect(screen.getByText('Piden asiento 5 personas y queda 1 asiento')).toBeVisible();
  });

  it('[driver_ui.AC-06] the strips use the singular and the plural correctly in Valencian (v1.2)', () => {
    const oneRequest = [
      stopDemand({ waiting: 1, needs: { RAMP: 0, EXTRA_TIME: 0, SEAT: 1, VISUAL: 0 } }),
    ];
    const { rerender } = renderWithProviders(
      <CapacityBanner
        view={driverView({
          capacity_alert: true,
          seat_alert: true,
          total_waiting: 1,
          free_places: 0,
          free_seats: 0,
          stops: oneRequest,
        })}
      />,
      { language: 'ca' },
    );
    expect(screen.getByText('Espera 1 persona i queden 0 places')).toBeVisible();
    expect(screen.getByText('Demana seient 1 persona i queden 0 seients')).toBeVisible();

    rerender(
      <CapacityBanner
        view={driverView({
          capacity_alert: true,
          seat_alert: true,
          total_waiting: 35,
          free_places: 1,
          free_seats: 1,
          stops: seatStops,
        })}
      />,
    );
    expect(screen.getByText('Esperen 35 persones i queda 1 plaça')).toBeVisible();
    expect(screen.getByText('Demanen seient 5 persones i queda 1 seient')).toBeVisible();
  });
});
