import { act, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { useRef } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { getDeviceId } from '../../../../shared/device/deviceId';
import { getNeedsProfile, setNeedsProfile } from '../../../../shared/device/needsProfile';
import type { Language } from '../../../../shared/i18n/languages';
import { FakeWebSocket } from '../../../../test/FakeWebSocket';
import { alertFixture } from '../../../../test/fixtures/alerts';
import { ARRIVALS_REALTIME } from '../../../../test/fixtures/api';
import {
  NetworkFailure,
  deferred,
  mockApi,
  problem,
  type FakeReply,
} from '../../../../test/mockApi';
import { renderWithProviders } from '../../../../test/render';
import { ArrivalsList } from '../../stop/ArrivalsList';
import { AlertsProvider } from '../AlertsProvider';

const NOW = new Date('2026-11-04T07:40:00Z');
const TOKEN = 'AbCdEfGhIjKlMnOpQrStUv';
const LABEL_93 = 'Solicitar parada a la línea 93 hacia Passeig Marítim - Hospital Malva-rosa';
const CREATED = alertFixture({ trip_id: '12345', needs: ['RAMP', 'SEAT'] });

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

function renderStop(language: Language = 'es') {
  const result = renderWithProviders(
    <MemoryRouter>
      <Stop />
    </MemoryRouter>,
    { language },
  );
  act(() => {
    FakeWebSocket.last().open();
    FakeWebSocket.last().receive({ type: 'alerts.snapshot', alerts: [] });
  });
  return result;
}

function card(index: number): HTMLElement {
  return screen.getAllByRole('listitem')[index]!;
}

function openDialog(name = LABEL_93, index = 1) {
  const button = within(card(index)).getByRole('button', { name });
  button.focus();
  fireEvent.click(button);
  return { button, dialog: screen.getByRole('dialog') };
}

function politeRegion(): HTMLElement {
  const region = document.querySelector<HTMLElement>('[aria-live="polite"]');
  if (region === null) throw new Error('no polite region');
  return region;
}

describe('RequestDialog', () => {
  let postReply: () => FakeReply | Promise<FakeReply>;
  let api: ReturnType<typeof mockApi>;

  beforeEach(() => {
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(true);
    postReply = () => ({ status: 201, body: CREATED });
    api = mockApi((url, init) => {
      if (url.pathname === '/api/v1/alerts' && init?.method === 'POST') return postReply();
      throw new Error(`unexpected request ${url.pathname}`);
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  function posts() {
    return api.fetchMock.mock.calls.filter(([, init]) => init?.method === 'POST');
  }

  it('[passenger_alert_ui.AC-04] "Solicitar" opens a modal dialog with the title, the arrival time and the needs preloaded', () => {
    setNeedsProfile(['RAMP', 'VISUAL']);
    const showModal = vi.spyOn(HTMLDialogElement.prototype, 'showModal');
    renderStop();

    const { dialog } = openDialog();

    expect(showModal).toHaveBeenCalledTimes(1);
    expect(dialog).toHaveAttribute('open');
    expect(dialog).toHaveAccessibleName(LABEL_93);
    const title = within(dialog).getByRole('heading', { level: 2, name: LABEL_93 });
    expect(title).toHaveFocus();
    expect(dialog).toHaveTextContent('El autobús llega en 4 minutos.');
    const needs = within(dialog).getByRole('group', { name: '¿Necesitas algo al subir?' });
    expect(within(needs).getByRole('checkbox', { name: 'Necesito la rampa' })).toBeChecked();
    expect(
      within(needs).getByRole('checkbox', { name: 'Tengo discapacidad visual' }),
    ).toBeChecked();
    expect(
      within(needs).getByRole('checkbox', { name: 'Necesito más tiempo para subir' }),
    ).not.toBeChecked();
    expect(within(needs).getByRole('checkbox', { name: 'Necesito un asiento' })).not.toBeChecked();
    expect(
      within(dialog).getByRole('checkbox', {
        name: 'Recordar mis necesidades en este dispositivo',
      }),
    ).not.toBeChecked();
    expect(within(dialog).getByRole('button', { name: 'Solicitar parada' })).toBeEnabled();
    expect(within(dialog).getByRole('button', { name: 'Volver' })).toBeEnabled();
    expect(posts()).toHaveLength(0);
  });

  it('[passenger_alert_ui.AC-04] titles the dialog in Valencian, with the destination marked as GTFS text', () => {
    renderStop('ca');

    const { dialog } = openDialog(
      'Sol·licita parada a la línia 93 cap a Passeig Marítim - Hospital Malva-rosa',
    );

    expect(dialog).toHaveAccessibleName(
      'Sol·licita parada a la línia 93 cap a Passeig Marítim - Hospital Malva-rosa',
    );
    expect(dialog).toHaveTextContent("L'autobús arriba en 4 minuts.");
    expect(
      within(dialog).getByRole('button', { name: 'Sol·licita la parada' }),
    ).toBeInTheDocument();
    expect(within(dialog).getByRole('button', { name: 'Torna' })).toBeInTheDocument();
  });

  it('[passenger_alert_ui.AC-04] says when the bus is arriving', () => {
    renderStop();

    const { dialog } = openDialog('Solicitar parada a la línea 70 hacia Alboraia', 0);

    expect(dialog).toHaveTextContent('El autobús está llegando.');
  });

  it('[passenger_alert_ui.AC-04] "Volver" closes without requesting and gives the focus back to "Solicitar"', () => {
    renderStop();
    const { button, dialog } = openDialog();

    fireEvent.click(within(dialog).getByRole('button', { name: 'Volver' }));

    expect(screen.queryByRole('dialog')).toBeNull();
    expect(button).toHaveFocus();
    expect(posts()).toHaveLength(0);
  });

  it('[passenger_alert_ui.AC-04] Escape closes without requesting and gives the focus back to "Solicitar"', () => {
    renderStop();
    const { button, dialog } = openDialog();

    fireEvent.keyDown(within(dialog).getByRole('checkbox', { name: 'Necesito la rampa' }), {
      key: 'Escape',
    });

    expect(screen.queryByRole('dialog')).toBeNull();
    expect(button).toHaveFocus();
    expect(posts()).toHaveLength(0);
  });

  it('[passenger_alert_ui.AC-05] sends POST /alerts with the bus of the card and the needs checked, showing "Enviando…" meanwhile', async () => {
    setNeedsProfile(['RAMP']);
    const reply = deferred<FakeReply>();
    postReply = () => reply.promise;
    renderStop();
    const { dialog } = openDialog();
    fireEvent.click(within(dialog).getByRole('checkbox', { name: 'Necesito un asiento' }));

    fireEvent.click(within(dialog).getByRole('button', { name: 'Solicitar parada' }));

    const sending = await within(dialog).findByRole('button', { name: 'Enviando…' });
    expect(sending).toBeDisabled();
    await waitFor(() => expect(posts()).toHaveLength(1));
    const [url, init] = posts()[0]!;
    expect(String(url)).toBe('/api/v1/alerts');
    expect(JSON.parse(String(init?.body))).toEqual({
      stop_id: '508',
      token: TOKEN,
      line: '93',
      direction_id: 0,
      trip_id: '12345',
      service_date: '2026-11-04',
      needs: ['RAMP', 'SEAT'],
    });
    expect(new Headers(init?.headers).get('X-Device-Id')).toBe(getDeviceId());
    // Without "Recordar" the profile is not changed.
    expect(getNeedsProfile()).toEqual(['RAMP']);

    await act(async () => reply.resolve({ status: 201, body: CREATED }));

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    await waitFor(() =>
      expect(politeRegion()).toHaveTextContent('Parada solicitada para la línea 93'),
    );
    expect(within(card(1)).getByRole('button', { name: 'Cancelar solicitud' })).toHaveFocus();
  });

  it('[passenger_alert_ui.AC-05] with "Recordar…" checked the needs become the profile of the device', async () => {
    renderStop();
    const { dialog } = openDialog();
    fireEvent.click(within(dialog).getByRole('checkbox', { name: 'Tengo discapacidad visual' }));
    fireEvent.click(
      within(dialog).getByRole('checkbox', {
        name: 'Recordar mis necesidades en este dispositivo',
      }),
    );

    fireEvent.click(within(dialog).getByRole('button', { name: 'Solicitar parada' }));

    expect(getNeedsProfile()).toEqual(['VISUAL']);
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  });

  it('[passenger_alert_ui.AC-05] a 200 (request already active) is also a success', async () => {
    postReply = () => ({ status: 200, body: CREATED });
    renderStop();
    const { dialog } = openDialog();

    fireEvent.click(within(dialog).getByRole('button', { name: 'Solicitar parada' }));

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    await waitFor(() =>
      expect(within(card(1)).getByRole('button', { name: 'Cancelar solicitud' })).toHaveFocus(),
    );
  });

  it.each([
    [
      '422',
      () => problem(422, 'https://avisabus/problems/bus-not-requestable'),
      'Este autobús ya no se puede solicitar.',
    ],
    [
      '429, Retry-After 125 s',
      () => ({ ...problem(429, 'x'), headers: { 'Retry-After': '125' } }),
      'Has hecho demasiadas solicitudes. Inténtalo dentro de 3 minutos.',
    ],
    [
      '429, Retry-After 60 s',
      () => ({ ...problem(429, 'x'), headers: { 'Retry-After': '60' } }),
      'Has hecho demasiadas solicitudes. Inténtalo dentro de 1 minuto.',
    ],
    [
      '429, Retry-After 1 s',
      () => ({ ...problem(429, 'x'), headers: { 'Retry-After': '1' } }),
      'Has hecho demasiadas solicitudes. Inténtalo dentro de 1 minuto.',
    ],
    [
      '404',
      () => problem(404, 'https://avisabus/problems/stop-not-found'),
      'La parada ya no está disponible. Vuelve a escanear el código QR.',
    ],
    [
      '503',
      () => problem(503, 'https://avisabus/problems/network-unavailable'),
      'No se ha podido enviar la solicitud. Comprueba la conexión.',
    ],
    [
      'a network error',
      () => {
        throw new NetworkFailure();
      },
      'No se ha podido enviar la solicitud. Comprueba la conexión.',
    ],
  ] as const)(
    '[passenger_alert_ui.AC-06] with %s the dialog stays open with a focused role="alert" message',
    async (_, reply, message) => {
      postReply = reply;
      renderStop();
      const { dialog } = openDialog();

      fireEvent.click(within(dialog).getByRole('button', { name: 'Solicitar parada' }));

      const alert = await within(dialog).findByRole('alert');
      expect(alert).toHaveTextContent(message);
      await waitFor(() => expect(alert).toHaveFocus());
      expect(screen.getByRole('dialog')).toHaveAttribute('open');
      expect(within(dialog).getByRole('button', { name: 'Solicitar parada' })).toBeEnabled();
    },
  );

  it('[passenger_alert_ui.AC-06] the 429 message is in Valencian too', async () => {
    postReply = () => ({ ...problem(429, 'x'), headers: { 'Retry-After': '600' } });
    renderStop('ca');
    const { dialog } = openDialog(
      'Sol·licita parada a la línia 93 cap a Passeig Marítim - Hospital Malva-rosa',
    );

    fireEvent.click(within(dialog).getByRole('button', { name: 'Sol·licita la parada' }));

    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      "Has fet massa sol·licituds. Torna-ho a intentar d'ací a 10 minuts.",
    );
  });

  it('[passenger_alert_ui.AC-06] a 422 refreshes the arrivals', async () => {
    postReply = () => problem(422, 'https://avisabus/problems/bus-not-requestable');
    const { queryClient } = renderStop();
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries');
    const { dialog } = openDialog();

    fireEvent.click(within(dialog).getByRole('button', { name: 'Solicitar parada' }));

    await within(dialog).findByRole('alert');
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['arrivals', '508'] });
  });

  it('[passenger_alert_ui.AC-06] after a network error "Solicitar parada" tries again', async () => {
    postReply = () => {
      throw new NetworkFailure();
    };
    renderStop();
    const { dialog } = openDialog();
    fireEvent.click(within(dialog).getByRole('button', { name: 'Solicitar parada' }));
    await within(dialog).findByRole('alert');

    postReply = () => ({ status: 201, body: CREATED });
    fireEvent.click(within(dialog).getByRole('button', { name: 'Solicitar parada' }));

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(posts()).toHaveLength(2);
  });
});
