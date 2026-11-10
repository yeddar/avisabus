import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { mockApi, NetworkFailure, ok, problem } from '../../../test/mockApi';
import {
  clearDriverToken,
  DriverAuthError,
  driverApi,
  getDriverToken,
  setDriverToken,
  subscribeDriverAuthLost,
} from '../session';

describe('driver session', () => {
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('[driver_ui.AC-01] keeps the token only in sessionStorage, under avisabus.driverSession', () => {
    setDriverToken('token-1');

    expect(getDriverToken()).toBe('token-1');
    expect(sessionStorage.getItem('avisabus.driverSession')).toBe('token-1');
    expect(localStorage.length).toBe(0);

    clearDriverToken();

    expect(getDriverToken()).toBeNull();
    expect(sessionStorage.getItem('avisabus.driverSession')).toBeNull();
  });

  it('[driver_ui.AC-01] sends the bearer token and a JSON body to the API', async () => {
    setDriverToken('token-1');
    const api = mockApi(() => ok({ value: 1 }));

    const result = await driverApi<{ value: number }>('PUT', '/driver/sessions/current/service', {
      line: '93',
    });

    expect(result).toEqual({ status: 200, data: { value: 1 }, retryAfterS: null });
    const [url, init] = api.fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe('/api/v1/driver/sessions/current/service');
    expect(init.method).toBe('PUT');
    expect(init.body).toBe(JSON.stringify({ line: '93' }));
    expect(new Headers(init.headers).get('Authorization')).toBe('Bearer token-1');
  });

  it('[driver_ui.AC-01] gives the status and the Retry-After seconds of an error response', async () => {
    mockApi(() => ({ ...problem(429, 'rate'), headers: { 'Retry-After': '120' } }));

    const result = await driverApi('POST', '/driver/sessions', { code: '12345678' });

    expect(result.status).toBe(429);
    expect(result.data).toBeNull();
    expect(result.retryAfterS).toBe(120);
  });

  it('[driver_ui.AC-03] a 401 clears the token, reports the lost session and throws DriverAuthError', async () => {
    setDriverToken('token-1');
    const listener = vi.fn();
    const unsubscribe = subscribeDriverAuthLost(listener);
    mockApi(() => problem(401, 'invalid-session'));

    await expect(driverApi('GET', '/driver/lines')).rejects.toBeInstanceOf(DriverAuthError);

    expect(getDriverToken()).toBeNull();
    expect(listener).toHaveBeenCalledTimes(1);
    unsubscribe();
  });

  it('[driver_ui.AC-03] a network failure does not end the session', async () => {
    setDriverToken('token-1');
    mockApi(() => {
      throw new NetworkFailure();
    });

    await expect(driverApi('GET', '/driver/lines')).rejects.toMatchObject({ status: 0 });

    expect(getDriverToken()).toBe('token-1');
  });
});
