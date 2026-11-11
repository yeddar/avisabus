import { fireEvent, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { mockApi, problem } from '../../../test/mockApi';
import { renderWithProviders } from '../../../test/render';
import { LoginPage } from '../LoginPage';
import { getDriverToken } from '../session';

function ShiftProbe() {
  const location = useLocation();
  return <p>at {location.pathname}</p>;
}

function renderLogin(initial: string | { pathname: string; state: unknown } = '/driver') {
  return renderWithProviders(
    <MemoryRouter initialEntries={[initial]}>
      <Routes>
        <Route path="/driver" element={<LoginPage />} />
        <Route path="/driver/shift" element={<ShiftProbe />} />
      </Routes>
    </MemoryRouter>,
  );
}

function codeField() {
  return screen.getByLabelText('Código de acceso');
}

describe('LoginPage', () => {
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('[driver_ui.AC-01] asks for the code in a numeric, one-time-code field with a visible label and Entrar', () => {
    renderLogin();

    const field = codeField();
    expect(field).toHaveAttribute('inputmode', 'numeric');
    expect(field).toHaveAttribute('autocomplete', 'one-time-code');
    expect(screen.getByText('Código de acceso').tagName).toBe('LABEL');
    expect(screen.getByRole('button', { name: 'Entrar' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Acceso de conductor');
  });

  it('[driver_ui.AC-01] groups the digits as "1234 5678" and ignores anything else', () => {
    renderLogin();

    fireEvent.change(codeField(), { target: { value: '12a3456 7899' } });

    expect(codeField()).toHaveValue('1234 5678');
  });

  it('[driver_ui.AC-01] with a 201 stores the token only in sessionStorage and goes to /driver/shift', async () => {
    const api = mockApi(() => ({
      status: 201,
      body: { session_id: 's', session_token: 'token-1', idle_timeout_s: 600 },
    }));
    renderLogin();

    fireEvent.change(codeField(), { target: { value: '12345678' } });
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }));

    expect(await screen.findByText('at /driver/shift')).toBeInTheDocument();
    expect(getDriverToken()).toBe('token-1');
    expect(localStorage.length).toBe(0);
    const [url, init] = api.fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/driver/sessions');
    expect(init.body).toBe(JSON.stringify({ code: '12345678' }));
  });

  it('[driver_ui.AC-01] with a 401 shows "Código no válido" and moves the focus to it', async () => {
    mockApi(() => problem(401, 'invalid-driver-code'));
    renderLogin();

    fireEvent.change(codeField(), { target: { value: '12345678' } });
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }));

    const message = await screen.findByText('Código no válido');
    await waitFor(() => expect(message).toHaveFocus());
    expect(getDriverToken()).toBeNull();
  });

  it('[driver_ui.AC-01] with a 429 tells how many minutes to wait, from Retry-After', async () => {
    mockApi(() => ({ ...problem(429, 'rate-limited'), headers: { 'Retry-After': '600' } }));
    renderLogin();

    fireEvent.change(codeField(), { target: { value: '12345678' } });
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }));

    expect(
      await screen.findByText('Demasiados intentos. Inténtalo dentro de 10 minutos.'),
    ).toBeInTheDocument();
  });

  it('[driver_ui.AC-10] shows the message of a closed shift', () => {
    renderLogin({ pathname: '/driver', state: { closedReason: 'REVOKED' } });

    expect(screen.getByText('Código revocado')).toBeInTheDocument();
  });

  it('[driver_ui.AC-01] does not call the API while the previous attempt is in flight', async () => {
    const api = mockApi(() => ({ status: 201, body: { session_token: 't' } }));
    renderLogin();

    fireEvent.change(codeField(), { target: { value: '12345678' } });
    const enter = screen.getByRole('button', { name: 'Entrar' });
    fireEvent.click(enter);
    fireEvent.click(enter);

    await screen.findByText('at /driver/shift');
    expect(api.fetchMock).toHaveBeenCalledTimes(1);
  });
});
