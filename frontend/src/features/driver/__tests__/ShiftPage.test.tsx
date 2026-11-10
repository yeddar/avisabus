import { screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { mockApi, ok, problem } from '../../../test/mockApi';
import { renderWithProviders } from '../../../test/render';
import { setDriverToken } from '../session';
import { ShiftPage } from '../ShiftPage';
import { driverView, LINE_93 } from './fixtures';

function LoginProbe() {
  const { pathname } = useLocation();
  return <p>at {pathname}</p>;
}

function renderShift() {
  return renderWithProviders(
    <MemoryRouter initialEntries={['/driver/shift']}>
      <Routes>
        <Route path="/driver" element={<LoginProbe />} />
        <Route path="/driver/shift" element={<ShiftPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('ShiftPage', () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('[driver_ui.AC-03] without a token it goes back to /driver without calling the API', async () => {
    const api = mockApi(() => ok({}));
    renderShift();

    expect(await screen.findByText('at /driver')).toBeInTheDocument();
    expect(api.fetchMock).not.toHaveBeenCalled();
  });

  it('[driver_ui.AC-03] a 401 from the current view goes back to /driver and forgets the token', async () => {
    setDriverToken('expired');
    mockApi(() => problem(401, 'invalid-session'));
    renderShift();

    expect(await screen.findByText('at /driver')).toBeInTheDocument();
    expect(sessionStorage.getItem('avisabus.driverSession')).toBeNull();
  });

  it('[driver_ui.AC-02] without a departure it shows the picker', async () => {
    setDriverToken('token-1');
    mockApi((url) => {
      if (url.pathname.endsWith('/current/view')) return ok(driverView({ service: null }));
      if (url.pathname.endsWith('/driver/lines')) return ok({ lines: [LINE_93] });
      return problem(500, 'unexpected');
    });
    renderShift();

    await screen.findByRole('heading', { level: 1, name: 'Elige la línea' });
  });

  it('[driver_ui.AC-03] a 401 while choosing goes back to /driver', async () => {
    setDriverToken('token-1');
    mockApi((url) => {
      if (url.pathname.endsWith('/current/view')) return ok(driverView({ service: null }));
      return problem(401, 'invalid-session');
    });
    renderShift();

    await waitFor(() => expect(screen.getByText('at /driver')).toBeInTheDocument());
  });
});
