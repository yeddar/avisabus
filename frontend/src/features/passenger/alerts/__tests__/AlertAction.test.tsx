import { act, screen, within } from '@testing-library/react';
import { useRef } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import type { Alert } from '../../../../shared/api/types';
import type { Language } from '../../../../shared/i18n/languages';
import { FakeWebSocket } from '../../../../test/FakeWebSocket';
import { alertFixture } from '../../../../test/fixtures/alerts';
import { ARRIVALS_REALTIME } from '../../../../test/fixtures/api';
import { renderWithProviders } from '../../../../test/render';
import { ArrivalsList } from '../../stop/ArrivalsList';
import { AlertsProvider } from '../AlertsProvider';

const NOW = new Date('2026-11-04T07:40:00Z');
const TOKEN = 'AbCdEfGhIjKlMnOpQrStUv';

const TEXTS = {
  es: {
    request: 'Solicitar',
    label93: 'Solicitar parada a la línea 93 hacia Passeig Marítim - Hospital Malva-rosa',
    label70: 'Solicitar parada a la línea 70 hacia Alboraia',
    otherBus: 'Ya has solicitado otro autobús de esta línea',
    pending: 'Parada solicitada. Aún no hay conductor conectado en esta línea.',
    delivered: 'El conductor ha recibido tu solicitud.',
    needs: 'Has indicado: rampa y asiento',
    cancel: 'Cancelar solicitud',
    map: 'Ver en el mapa',
  },
  ca: {
    request: 'Sol·licita',
    label93: 'Sol·licita parada a la línia 93 cap a Passeig Marítim - Hospital Malva-rosa',
    label70: 'Sol·licita parada a la línia 70 cap a Alboraia',
    otherBus: "Ja has sol·licitat un altre autobús d'esta línia",
    pending: 'Parada sol·licitada. Encara no hi ha cap conductor connectat en esta línia.',
    delivered: 'El conductor ha rebut la teua sol·licitud.',
    needs: 'Has indicat: rampa i seient',
    cancel: 'Cancel·la la sol·licitud',
    map: 'Mostra en el mapa',
  },
} as const;

function Stop() {
  const heading = useRef<HTMLHeadingElement>(null);
  return (
    <AlertsProvider fallbackFocus={heading}>
      <h2 ref={heading} tabIndex={-1}>
        arrivals
      </h2>
      <ArrivalsList
        arrivals={ARRIVALS_REALTIME().arrivals}
        source="REALTIME"
        now={NOW}
        stopId="508"
        token={TOKEN}
      />
    </AlertsProvider>
  );
}

/** Renders the arrivals of stop 508 with `alerts` as the snapshot of the WebSocket. */
function renderStop(alerts: Alert[], language: Language = 'es') {
  renderWithProviders(
    <MemoryRouter>
      <Stop />
    </MemoryRouter>,
    { language },
  );
  act(() => {
    FakeWebSocket.last().open();
    FakeWebSocket.last().receive({ type: 'alerts.snapshot', alerts });
  });
  return screen.getAllByRole('listitem');
}

describe('AlertAction and AlertStatus in the arrival cards', () => {
  beforeEach(() => {
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(true);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it.each(['es', 'ca'] as const)(
    '[passenger_alert_ui.AC-03] shows "Solicitar" with line and spoken destination only where can_alert is true (%s)',
    (language) => {
      const texts = TEXTS[language];
      const items = renderStop([], language);

      // Cards: 0 = 70 arriving, 1 = 93 in 4 min, 2 = 70 without vehicle, 3 = 93 in 16 min, 4 = N4.
      const button = (index: number) =>
        within(items[index]!).queryByRole('button', { name: new RegExp(`^${texts.request}`) });
      expect(button(0)).toHaveAccessibleName(texts.label70);
      expect(button(1)).toHaveAccessibleName(texts.label93);
      expect(button(3)).toHaveAccessibleName(texts.label93);
      expect(button(2)).toBeNull();
      expect(button(4)).toBeNull();
      expect(button(1)).toHaveTextContent(texts.request);
      expect(within(items[1]!).getByRole('link', { name: new RegExp(texts.map) })).toBeVisible();
    },
  );

  it.each(['es', 'ca'] as const)(
    '[passenger_alert_ui.AC-03] with an alert for another bus of the line, the other cards of that line say so instead of the button (%s)',
    (language) => {
      const texts = TEXTS[language];
      const items = renderStop([alertFixture({ trip_id: '12345' })], language);

      const other = items[3]!;
      expect(within(other).queryByRole('button', { name: new RegExp(texts.request) })).toBeNull();
      expect(within(other).getByText(texts.otherBus)).toBeInTheDocument();
      // Other lines are not affected.
      expect(within(items[0]!).getByRole('button', { name: texts.label70 })).toBeInTheDocument();
      expect(within(items[0]!).queryByText(texts.otherBus)).toBeNull();
      // A card without can_alert shows nothing.
      expect(within(items[2]!).queryByText(texts.otherBus)).toBeNull();
    },
  );

  it('[passenger_alert_ui.AC-03] an alert at another stop does not change the cards', () => {
    const items = renderStop([alertFixture({ stop_id: '1234', trip_id: '12345' })]);

    expect(within(items[1]!).getByRole('button', { name: TEXTS.es.label93 })).toBeInTheDocument();
    expect(within(items[3]!).getByRole('button', { name: TEXTS.es.label93 })).toBeInTheDocument();
    expect(screen.queryByText(TEXTS.es.otherBus)).toBeNull();
  });

  it('[passenger_alert_ui.AC-03] the same trip on another service day is another bus', () => {
    const items = renderStop([alertFixture({ trip_id: '12345', service_date: '2026-11-03' })]);

    expect(within(items[1]!).queryByText(TEXTS.es.cancel)).toBeNull();
    expect(within(items[1]!).getByText(TEXTS.es.otherBus)).toBeInTheDocument();
  });

  it.each(['es', 'ca'] as const)(
    '[passenger_alert_ui.AC-07] the card of the requested bus shows the status, the needs and "Cancelar solicitud" (%s)',
    (language) => {
      const texts = TEXTS[language];
      const items = renderStop(
        [alertFixture({ trip_id: '12345', needs: ['RAMP', 'SEAT'] })],
        language,
      );

      const card = items[1]!;
      expect(
        within(card).queryByRole('button', { name: new RegExp(`^${texts.request}`) }),
      ).toBeNull();
      expect(card).toHaveTextContent(texts.pending);
      expect(within(card).getByText(texts.needs)).toBeInTheDocument();
      expect(within(card).getByRole('button', { name: texts.cancel })).toBeInTheDocument();
      // "Ver en el mapa" stays above the status box (docs/design.md §5.8).
      const map = within(card).getByRole('link', { name: new RegExp(texts.map) });
      const cancel = within(card).getByRole('button', { name: texts.cancel });
      expect(map.compareDocumentPosition(cancel) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    },
  );

  it.each(['es', 'ca'] as const)(
    '[passenger_alert_ui.AC-07] DELIVERED says that the driver has received the request (%s)',
    (language) => {
      const texts = TEXTS[language];
      const items = renderStop([alertFixture({ trip_id: '12345', status: 'DELIVERED' })], language);

      expect(items[1]!).toHaveTextContent(texts.delivered);
      expect(items[1]!).not.toHaveTextContent(texts.pending);
    },
  );

  it('[passenger_alert_ui.AC-07] without needs there is no "Has indicado"', () => {
    const items = renderStop([alertFixture({ trip_id: '12345', needs: [] })]);

    expect(items[1]!).toHaveTextContent(TEXTS.es.pending);
    expect(items[1]!).not.toHaveTextContent('Has indicado');
  });

  it('[passenger_alert_ui.AC-07] the status replaces the button as soon as an event registers the alert', () => {
    const items = renderStop([]);
    expect(within(items[1]!).getByRole('button', { name: TEXTS.es.label93 })).toBeInTheDocument();

    act(() =>
      FakeWebSocket.last().receive({
        type: 'alert.registered',
        alert: alertFixture({ trip_id: '12345' }),
      }),
    );

    expect(within(items[1]!).queryByRole('button', { name: TEXTS.es.label93 })).toBeNull();
    expect(within(items[1]!).getByRole('button', { name: TEXTS.es.cancel })).toBeInTheDocument();
  });
});
