import { act, fireEvent, screen, within } from '@testing-library/react';
import { RouterProvider, createMemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { routes } from '../../../../app/routes';
import type { Alert } from '../../../../shared/api/types';
import { getDeviceId } from '../../../../shared/device/deviceId';
import type { Language } from '../../../../shared/i18n/languages';
import { FakeWebSocket } from '../../../../test/FakeWebSocket';
import { alert70, alertFixture } from '../../../../test/fixtures/alerts';
import { ARRIVALS_REALTIME, STOP_508 } from '../../../../test/fixtures/api';
import {
  NetworkFailure,
  deferred,
  mockApi,
  ok,
  problem,
  type FakeReply,
} from '../../../../test/mockApi';
import { renderWithProviders } from '../../../../test/render';

const TOKEN = 'AbCdEfGhIjKlMnOpQrStUv';
const GENERATED_AT = Date.parse('2026-11-04T07:40:00Z');
const LABEL_93 = 'Solicitar parada a la línea 93 hacia Passeig Marítim - Hospital Malva-rosa';
const ON_CARD = alertFixture({ trip_id: '12345' });
/** A request of line 93 whose bus is no longer among the arrivals. */
const ORPHAN = alertFixture({
  alert_id: '9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d',
  trip_id: '12300',
  status: 'DELIVERED',
  needs: ['VISUAL'],
});

function renderStop(language: Language = 'es') {
  const router = createMemoryRouter(routes, { initialEntries: [`/p/508?t=${TOKEN}`] });
  return renderWithProviders(<RouterProvider router={router} />, { language });
}

async function flush(ms = 0) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

function politeRegion(): HTMLElement {
  const region = document.querySelector<HTMLElement>('[aria-live="polite"]');
  if (region === null) throw new Error('no polite region');
  return region;
}

function arrivalsHeading(name = 'Próximas llegadas'): HTMLElement {
  return screen.getByRole('heading', { level: 2, name });
}

function arrivalsSection(): HTMLElement {
  return arrivalsHeading().closest('section')!;
}

function card(index: number): HTMLElement {
  return within(arrivalsSection()).getAllByRole('listitem')[index]!;
}

function receive(message: unknown) {
  act(() => FakeWebSocket.last().receive(message));
}

describe('StopPage with stop requests', () => {
  let deleteReply: () => FakeReply;
  let api: ReturnType<typeof mockApi>;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(GENERATED_AT);
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(true);
    deleteReply = () => ({ status: 204, body: null });
    api = mockApi((url, init) => {
      if (url.pathname === '/api/v1/stops/508') return ok(STOP_508());
      if (url.pathname === '/api/v1/stops/508/arrivals') return ok(ARRIVALS_REALTIME());
      if (url.pathname.startsWith('/api/v1/alerts/') && init?.method === 'DELETE') {
        return deleteReply();
      }
      throw new Error(`unexpected request ${url.pathname}`);
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    localStorage.clear();
    document.title = '';
  });

  async function openWith(alerts: Alert[], language: Language = 'es') {
    renderStop(language);
    await flush();
    act(() => FakeWebSocket.last().open());
    receive({ type: 'alerts.snapshot', alerts });
    await flush();
  }

  function deletes() {
    return api.fetchMock.mock.calls.filter(([, init]) => init?.method === 'DELETE');
  }

  it('[passenger_alert_ui.AC-10] opens /ws/passenger with the stop view and sends the hello', async () => {
    renderStop();
    await flush();

    expect(FakeWebSocket.instances).toHaveLength(1);
    act(() => FakeWebSocket.last().open());
    expect(FakeWebSocket.last().sentMessages()).toEqual([
      { type: 'hello', device_id: getDeviceId() },
    ]);
  });

  it('[passenger_alert_ui.AC-08] shows above the arrivals a request whose bus is no longer in the list', async () => {
    await openWith([ORPHAN, alertFixture({ alert_id: 'x', stop_id: '1234', line: '70' })]);

    const section = arrivalsSection();
    const title = within(section).getByText(
      (_, element) =>
        element?.tagName === 'P' &&
        element.textContent === 'Línea 93 hacia Passeig Marítim - Hospital Malva-rosa',
    );
    // Title → text column → icon row → status box.
    const notice = title.parentElement!.parentElement!.parentElement!;
    expect(notice).toHaveTextContent('El conductor ha recibido tu solicitud.');
    expect(notice).toHaveTextContent('Has indicado: discapacidad visual');
    const cancel = within(notice).getByRole('button', { name: 'Cancelar solicitud' });
    const list = within(section).getByRole('list');
    expect(cancel.compareDocumentPosition(list) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(notice).getByText('Passeig Marítim - Hospital Malva-rosa')).toHaveAttribute(
      'lang',
      'ca-ES-valencia',
    );
    // Only requests of this stop; the card of the other line 93 bus says it is already requested.
    expect(within(section).getAllByRole('button', { name: 'Cancelar solicitud' })).toHaveLength(1);
    expect(card(1)).toHaveTextContent('Ya has solicitado otro autobús de esta línea');
  });

  it('[passenger_alert_ui.AC-08] a request shown in its card is not repeated above the list', async () => {
    await openWith([ON_CARD]);

    expect(screen.getAllByRole('button', { name: 'Cancelar solicitud' })).toHaveLength(1);
    expect(within(card(1)).getByRole('button', { name: 'Cancelar solicitud' })).toBeInTheDocument();
    expect(arrivalsSection()).not.toHaveTextContent(
      'Línea 93 hacia Passeig Marítim - Hospital Malva-rosa',
    );
  });

  it('[passenger_alert_ui.AC-08] shows the request in Valencian', async () => {
    await openWith([ORPHAN], 'ca');

    const section = arrivalsHeading('Pròximes arribades').closest('section')!;
    expect(section).toHaveTextContent('Línia 93 cap a Passeig Marítim - Hospital Malva-rosa');
    expect(section).toHaveTextContent('El conductor ha rebut la teua sol·licitud.');
    expect(within(section).getByRole('button', { name: 'Cancel·la la sol·licitud' })).toBeVisible();
  });

  it('[passenger_alert_ui.AC-09] "Cancelar solicitud" sends DELETE without confirmation and gives the focus to "Solicitar" of the card', async () => {
    await openWith([ON_CARD]);
    const cancel = within(card(1)).getByRole('button', { name: 'Cancelar solicitud' });
    cancel.focus();

    fireEvent.click(cancel);
    expect(screen.queryByRole('dialog')).toBeNull();
    await flush(100);

    expect(deletes()).toHaveLength(1);
    const [url, init] = deletes()[0]!;
    expect(String(url)).toBe(`/api/v1/alerts/${ON_CARD.alert_id}`);
    expect(new Headers(init?.headers).get('X-Device-Id')).toBe(getDeviceId());
    expect(within(card(1)).queryByRole('button', { name: 'Cancelar solicitud' })).toBeNull();
    expect(politeRegion()).toHaveTextContent('Solicitud cancelada');
    expect(within(card(1)).getByRole('button', { name: LABEL_93 })).toHaveFocus();
  });

  it('[passenger_alert_ui.AC-09] a 404 removes the request too and says it was no longer active', async () => {
    deleteReply = () => problem(404, 'https://avisabus/problems/alert-not-found');
    await openWith([ON_CARD]);
    within(card(1)).getByRole('button', { name: 'Cancelar solicitud' }).focus();

    fireEvent.click(within(card(1)).getByRole('button', { name: 'Cancelar solicitud' }));
    await flush(100);

    expect(within(card(1)).queryByRole('button', { name: 'Cancelar solicitud' })).toBeNull();
    expect(politeRegion()).toHaveTextContent('La solicitud ya no estaba activa');
    expect(within(card(1)).getByRole('button', { name: LABEL_93 })).toHaveFocus();
  });

  it('[passenger_alert_ui.AC-09] cancelling a request without card moves the focus to "Próximas llegadas"', async () => {
    await openWith([ORPHAN]);

    fireEvent.click(screen.getByRole('button', { name: 'Cancelar solicitud' }));
    await flush(100);

    expect(screen.queryByRole('button', { name: 'Cancelar solicitud' })).toBeNull();
    expect(arrivalsHeading()).toHaveFocus();
    expect(politeRegion()).toHaveTextContent('Solicitud cancelada');
  });

  it('[passenger_alert_ui.AC-09] a network error keeps the request and the focus, and says so', async () => {
    deleteReply = () => {
      throw new NetworkFailure();
    };
    await openWith([ON_CARD]);
    const cancel = within(card(1)).getByRole('button', { name: 'Cancelar solicitud' });
    cancel.focus();

    fireEvent.click(cancel);
    await flush(100);

    expect(politeRegion()).toHaveTextContent('No se ha podido cancelar la solicitud');
    expect(cancel).toBeInTheDocument();
    expect(cancel).toHaveFocus();
  });

  it('[passenger_alert_ui.AC-11] an expiry announces the reason and moves the focus from "Cancelar solicitud" to "Solicitar"', async () => {
    await openWith([ON_CARD]);
    within(card(1)).getByRole('button', { name: 'Cancelar solicitud' }).focus();

    receive({ type: 'alert.expired', alert_id: ON_CARD.alert_id, reason: 'PASSED' });
    await flush(100);

    expect(politeRegion()).toHaveTextContent(
      'Tu solicitud de la línea 93 ha terminado: el autobús ha pasado por la parada',
    );
    expect(within(card(1)).getByRole('button', { name: LABEL_93 })).toHaveFocus();
  });

  it('[passenger_alert_ui.AC-11] a cancellation from another tab is silent; the focus goes to "Próximas llegadas" without "Solicitar"', async () => {
    await openWith([ORPHAN]);
    screen.getByRole('button', { name: 'Cancelar solicitud' }).focus();

    receive({ type: 'alert.cancelled', alert_id: ORPHAN.alert_id });
    await flush(100);

    expect(politeRegion()).toHaveTextContent('');
    expect(arrivalsHeading()).toHaveFocus();
  });

  it('[passenger_alert_ui.AC-11] a delivery is announced and updates the card', async () => {
    await openWith([ON_CARD]);

    receive({ type: 'alert.delivered', alert: { ...ON_CARD, status: 'DELIVERED' } });
    await flush(100);

    expect(politeRegion()).toHaveTextContent(
      'El conductor de la línea 93 ha recibido tu solicitud',
    );
    expect(card(1)).toHaveTextContent('El conductor ha recibido tu solicitud.');
  });

  it('[passenger_alert_ui.AC-11] the focus elsewhere stays where it is when a request goes away', async () => {
    await openWith([ON_CARD, alert70()]);
    const other = within(card(0)).getByRole('button', { name: 'Cancelar solicitud' });
    other.focus();

    receive({ type: 'alert.expired', alert_id: ON_CARD.alert_id, reason: 'TIMEOUT' });
    await flush(100);

    expect(other).toHaveFocus();
  });

  describe('with the request dialog open', () => {
    function cancelIn(element: HTMLElement): HTMLElement {
      return within(element).getByRole('button', { name: 'Cancelar solicitud' });
    }

    function openDialogIn(index: number): HTMLElement {
      fireEvent.click(within(card(index)).getByRole('button', { name: LABEL_93 }));
      return screen.getByRole('dialog');
    }

    it('[passenger_alert_ui.AC-11] alert.registered of the same stop and line closes it and moves the focus to "Cancelar solicitud" of its card, silently', async () => {
      await openWith([]);
      openDialogIn(1);

      receive({ type: 'alert.registered', alert: ON_CARD });
      await flush(100);

      expect(screen.queryByRole('dialog')).toBeNull();
      expect(cancelIn(card(1))).toHaveFocus();
      expect(politeRegion()).toHaveTextContent('');
    });

    it('[passenger_alert_ui.AC-11] alert.delivered closes it too, with only the announcement of the delivery', async () => {
      await openWith([]);
      openDialogIn(1);

      receive({ type: 'alert.delivered', alert: { ...ON_CARD, status: 'DELIVERED' } });
      await flush(100);

      expect(screen.queryByRole('dialog')).toBeNull();
      expect(cancelIn(card(1))).toHaveFocus();
      expect(politeRegion().textContent).toBe(
        'El conductor de la línea 93 ha recibido tu solicitud',
      );
    });

    it('[passenger_alert_ui.AC-11] a request for another bus of the line moves the focus to the card of that bus', async () => {
      await openWith([]);
      openDialogIn(3);

      receive({ type: 'alert.registered', alert: ON_CARD });
      await flush(100);

      expect(screen.queryByRole('dialog')).toBeNull();
      expect(cancelIn(card(1))).toHaveFocus();
      expect(card(3)).toHaveTextContent('Ya has solicitado otro autobús de esta línea');
    });

    it('[passenger_alert_ui.AC-11] a request whose bus is not in the list moves the focus to its notice above the arrivals', async () => {
      await openWith([]);
      openDialogIn(1);

      receive({ type: 'alert.registered', alert: ORPHAN });
      await flush(100);

      expect(screen.queryByRole('dialog')).toBeNull();
      expect(cancelIn(arrivalsSection())).toHaveFocus();
    });

    it('[passenger_alert_ui.AC-11] the dialog closed by another tab does not come back when that request ends', async () => {
      await openWith([]);
      openDialogIn(3);
      receive({ type: 'alert.registered', alert: ON_CARD });
      await flush(100);

      receive({ type: 'alert.cancelled', alert_id: ON_CARD.alert_id });
      await flush(100);

      expect(within(card(3)).getByRole('button', { name: LABEL_93 })).toBeVisible();
      expect(screen.queryByRole('dialog')).toBeNull();
    });

    it('[passenger_alert_ui.AC-11] the event of the own request arriving before the response of the POST also moves the focus', async () => {
      const reply = deferred<FakeReply>();
      mockApi((url, init) => {
        if (url.pathname === '/api/v1/stops/508') return ok(STOP_508());
        if (url.pathname === '/api/v1/stops/508/arrivals') return ok(ARRIVALS_REALTIME());
        if (url.pathname === '/api/v1/alerts' && init?.method === 'POST') return reply.promise;
        throw new Error(`unexpected request ${url.pathname}`);
      });
      await openWith([]);
      const dialog = openDialogIn(1);
      fireEvent.click(within(dialog).getByRole('button', { name: 'Solicitar parada' }));
      await flush();

      receive({ type: 'alert.registered', alert: ON_CARD });
      await flush(100);

      expect(screen.queryByRole('dialog')).toBeNull();
      expect(cancelIn(card(1))).toHaveFocus();
      expect(politeRegion()).toHaveTextContent('');

      reply.resolve({ status: 201, body: ON_CARD });
      await flush(100);

      expect(politeRegion().textContent).toBe('Parada solicitada para la línea 93');
      expect(cancelIn(card(1))).toHaveFocus();
    });

    it.each([
      ['another line', alert70()],
      ['another stop', alertFixture({ alert_id: 'x', stop_id: '1234', trip_id: '999' })],
    ])(
      '[passenger_alert_ui.AC-11] a request of %s leaves it open with the focus inside',
      async (_case, alert) => {
        await openWith([]);
        const dialog = openDialogIn(1);
        const title = within(dialog).getByRole('heading', { level: 2, name: LABEL_93 });

        receive({ type: 'alert.registered', alert });
        await flush(100);

        expect(screen.getByRole('dialog')).toBe(dialog);
        expect(title).toHaveFocus();
      },
    );
  });

  it('[passenger_alert_ui.AC-06] a 422 on the request refreshes the arrivals', async () => {
    api = mockApi((url, init) => {
      if (url.pathname === '/api/v1/stops/508') return ok(STOP_508());
      if (url.pathname === '/api/v1/stops/508/arrivals') return ok(ARRIVALS_REALTIME());
      if (url.pathname === '/api/v1/alerts' && init?.method === 'POST') {
        return problem(422, 'https://avisabus/problems/bus-not-requestable');
      }
      throw new Error(`unexpected request ${url.pathname}`);
    });
    await openWith([]);
    expect(api.arrivalCalls()).toBe(1);

    fireEvent.click(within(card(1)).getByRole('button', { name: LABEL_93 }));
    fireEvent.click(screen.getByRole('button', { name: 'Solicitar parada' }));
    await flush(100);

    expect(within(screen.getByRole('dialog')).getByRole('alert')).toHaveTextContent(
      'Este autobús ya no se puede solicitar.',
    );
    expect(api.arrivalCalls()).toBe(2);
  });
});
