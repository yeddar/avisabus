import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import type { Arrival } from '../../../../shared/api/types';
import { ARRIVALS_REALTIME } from '../../../../test/fixtures/api';
import { renderWithProviders } from '../../../../test/render';
import { ArrivalTime } from '../ArrivalTime';
import { currentMinutes } from '../countdown';

const GENERATED = new Date('2026-11-04T07:40:00Z');

function minutesArrival(minutes: number): Arrival {
  const base = ARRIVALS_REALTIME().arrivals[1]!;
  return {
    ...base,
    kind: 'MINUTES',
    minutes,
    arrival_at: new Date(GENERATED.getTime() + minutes * 60_000).toISOString(),
  };
}

function clockArrival(iso: string): Arrival {
  return { ...ARRIVALS_REALTIME().arrivals[4]!, arrival_at: iso };
}

describe('ArrivalTime', () => {
  it.each([
    [1, '1 min'],
    [4, '4 min'],
    [25, '25 min'],
  ])('[passenger_stop_view.AC-06] shows MINUTES %i as "%s"', (minutes, text) => {
    const { container } = renderWithProviders(
      <ArrivalTime arrival={minutesArrival(minutes)} now={GENERATED} scheduled={false} />,
    );

    expect(container).toHaveTextContent(new RegExp(`^${text}$`));
  });

  it.each([
    ['es', 'Llegando'],
    ['ca', 'Arribant'],
  ] as const)('[passenger_stop_view.AC-06] shows MINUTES 0 as "%s" in %s', (language, text) => {
    const { container } = renderWithProviders(
      <ArrivalTime arrival={minutesArrival(0)} now={GENERATED} scheduled={false} />,
      { language },
    );

    expect(container).toHaveTextContent(new RegExp(`^${text}$`));
  });

  it('[passenger_stop_view.AC-06] shows CLOCK_TIME as HH:MM in Europe/Madrid', () => {
    const { container } = renderWithProviders(
      <ArrivalTime
        arrival={clockArrival('2026-11-04T21:41:00Z')}
        now={GENERATED}
        scheduled={false}
      />,
    );

    expect(container).toHaveTextContent(/^22:41$/);
  });

  it('[passenger_stop_view.AC-09] marks scheduled times as "programado"', () => {
    renderWithProviders(
      <ArrivalTime arrival={clockArrival('2026-11-04T07:52:00Z')} now={GENERATED} scheduled />,
    );

    expect(screen.getByText('08:52')).toBeInTheDocument();
    expect(screen.getByText('programado')).toBeInTheDocument();
  });

  it('[passenger_stop_view.AC-13] counts down from arrival_at with the server time', () => {
    const arrival = minutesArrival(4);
    const later = new Date(GENERATED.getTime() + 75_000);

    renderWithProviders(<ArrivalTime arrival={arrival} now={later} scheduled={false} />);

    // 2 min 45 s left: shown as 3 min.
    expect(screen.getByText('3')).toBeInTheDocument();
  });
});

describe('currentMinutes', () => {
  it('[passenger_stop_view.AC-13] rounds the remaining time up and never exceeds the API minutes', () => {
    const arrival = minutesArrival(4);
    const at = (seconds: number) => new Date(GENERATED.getTime() + seconds * 1000);

    expect(currentMinutes(arrival, at(0))).toBe(4);
    expect(currentMinutes(arrival, at(-30))).toBe(4);
    expect(currentMinutes(arrival, at(15))).toBe(4);
    expect(currentMinutes(arrival, at(60))).toBe(3);
    expect(currentMinutes(arrival, at(181))).toBe(1);
    expect(currentMinutes(arrival, at(240))).toBe(0);
    expect(currentMinutes(arrival, at(600))).toBe(0);
  });

  it('[passenger_stop_view.AC-13] returns null for CLOCK_TIME arrivals', () => {
    expect(currentMinutes(clockArrival('2026-11-04T21:41:00Z'), GENERATED)).toBeNull();
  });
});
