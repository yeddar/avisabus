import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { API_TIMEOUT_MS, ApiError, apiGet, apiSend } from '../client';
import { getDeviceId } from '../../device/deviceId';
import type { StopResponse } from '../types';

const STOP: StopResponse = {
  stop_id: '508',
  name: "Parc de l'Oest - Enguera",
  lines: [
    {
      line: '93',
      direction_id: 0,
      headsign: 'Passeig Marítim - Hospital Malva-rosa',
      color: 'FE0000',
      text_color: 'FFFFFF',
    },
  ],
};

function json(body: unknown, status = 200, contentType = 'application/json'): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': contentType } });
}

function problem(status: number, type: string): Response {
  return json({ type, title: 'x', status }, status, 'application/problem+json');
}

/** A fetch that only settles when its signal is aborted (like a request that never answers). */
function hangingFetch() {
  return vi.fn(
    (_input: RequestInfo | URL, init?: RequestInit) =>
      new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => {
          reject(new DOMException('The operation was aborted.', 'AbortError'));
        });
      }),
  );
}

async function caught(promise: Promise<unknown>): Promise<unknown> {
  try {
    await promise;
  } catch (error) {
    return error;
  }
  throw new Error('expected a rejection');
}

describe('apiGet', () => {
  const fetchMock = vi.fn<typeof fetch>();

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it('[passenger_stop_view.AC-03] requests /api/v1 with Accept JSON and returns the typed body', async () => {
    fetchMock.mockResolvedValue(json(STOP));

    const stop = await apiGet<StopResponse>('/stops/508?t=abc');

    expect(stop).toEqual(STOP);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] ?? [];
    expect(url).toBe('/api/v1/stops/508?t=abc');
    expect(new Headers(init?.headers).get('Accept')).toBe('application/json');
    expect(init?.signal).toBeInstanceOf(AbortSignal);
  });

  it.each([
    [404, 'https://avisabus/problems/stop-not-found'],
    [503, 'https://avisabus/problems/network-unavailable'],
  ])(
    '[passenger_stop_view.AC-03] turns a problem+json %i into an ApiError with status and type',
    async (status, type) => {
      fetchMock.mockResolvedValue(problem(status, type));

      const error = await caught(apiGet('/stops/508?t=abc'));

      expect(error).toBeInstanceOf(ApiError);
      expect(error).toMatchObject({ status, type });
    },
  );

  it('[passenger_stop_view.AC-03] uses a null type when the error body is not problem+json', async () => {
    fetchMock.mockResolvedValue(
      new Response('<h1>Bad gateway</h1>', {
        status: 502,
        headers: { 'Content-Type': 'text/html' },
      }),
    );

    const error = await caught(apiGet('/stops/508'));

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 502, type: null });
  });

  it('[passenger_stop_view.AC-03] uses a null type when a problem+json body is malformed', async () => {
    fetchMock.mockResolvedValue(
      new Response('{not json', {
        status: 503,
        headers: { 'Content-Type': 'application/problem+json' },
      }),
    );

    const error = await caught(apiGet('/stops/508'));

    expect(error).toMatchObject({ status: 503, type: null });
  });

  it('[passenger_stop_view.AC-03] turns a network error into an ApiError with status 0', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));

    const error = await caught(apiGet('/stops/508'));

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 0, type: 'network' });
  });

  it('[passenger_stop_view.AC-03] gives up after 8 s with an ApiError with status 0', async () => {
    vi.useFakeTimers();
    const hanging = hangingFetch();
    vi.stubGlobal('fetch', hanging);
    const settled = vi.fn();

    const result = apiGet('/stops/508').then(settled, (error: unknown) => {
      settled(error);
      return error;
    });

    await vi.advanceTimersByTimeAsync(API_TIMEOUT_MS - 1);
    expect(API_TIMEOUT_MS).toBe(8_000);
    expect(settled).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(1);
    const error = await result;
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 0, type: 'network' });
  });

  it('[passenger_stop_view.AC-03] aborts the request when the caller signal is aborted', async () => {
    const hanging = hangingFetch();
    vi.stubGlobal('fetch', hanging);
    const controller = new AbortController();

    const result = caught(apiGet('/stops/508', { signal: controller.signal }));
    controller.abort();

    const error = await result;
    expect(error).not.toBeInstanceOf(ApiError);
    expect((error as DOMException).name).toBe('AbortError');
  });

  it('[passenger_stop_view.AC-03] treats an unreadable success body as a network error', async () => {
    fetchMock.mockResolvedValue(new Response('{oops', { status: 200 }));

    const error = await caught(apiGet('/stops/508'));

    expect(error).toMatchObject({ status: 0, type: 'network' });
  });
});

describe('apiSend', () => {
  const fetchMock = vi.fn<typeof fetch>();
  const BODY = { stop_id: '508', needs: ['RAMP'] };

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it('[passenger_alert_ui.AC-01] sends the device identifier only in X-Device-Id, with a JSON body', async () => {
    fetchMock.mockResolvedValue(json({ alert_id: 'a' }, 201));

    const result = await apiSend<{ alert_id: string }>('POST', '/alerts', BODY);

    expect(result).toEqual({ status: 201, data: { alert_id: 'a' }, retryAfterS: null });
    const [url, init] = fetchMock.mock.calls[0] ?? [];
    expect(url).toBe('/api/v1/alerts');
    expect(init?.method).toBe('POST');
    const headers = new Headers(init?.headers);
    expect(headers.get('X-Device-Id')).toBe(getDeviceId());
    expect(headers.get('Content-Type')).toBe('application/json');
    expect(headers.get('Accept')).toBe('application/json');
    expect(init?.body).toBe(JSON.stringify(BODY));
    expect(String(url)).not.toContain(getDeviceId());
    expect(String(init?.body)).not.toContain(getDeviceId());
  });

  it('[passenger_alert_ui.AC-01] DELETE without body: no Content-Type, 204 gives null data', async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));

    const result = await apiSend('DELETE', '/alerts/6f1c');

    expect(result).toEqual({ status: 204, data: null, retryAfterS: null });
    const [url, init] = fetchMock.mock.calls[0] ?? [];
    expect(url).toBe('/api/v1/alerts/6f1c');
    expect(init?.method).toBe('DELETE');
    expect(init?.body).toBeUndefined();
    const headers = new Headers(init?.headers);
    expect(headers.get('X-Device-Id')).toBe(getDeviceId());
    expect(headers.has('Content-Type')).toBe(false);
  });

  it('[passenger_alert_ui.AC-01] GET /alerts/mine also identifies the device with the header only', async () => {
    fetchMock.mockResolvedValue(json({ alerts: [] }));

    const result = await apiSend('GET', '/alerts/mine');

    expect(result.data).toEqual({ alerts: [] });
    const [url, init] = fetchMock.mock.calls[0] ?? [];
    expect(url).toBe('/api/v1/alerts/mine');
    expect(new Headers(init?.headers).get('X-Device-Id')).toBe(getDeviceId());
  });

  it('[passenger_alert_ui.AC-06] a 429 is an ApiError with the Retry-After seconds', async () => {
    fetchMock.mockResolvedValue(
      new Response(
        JSON.stringify({ type: 'https://avisabus/problems/rate-limited', status: 429 }),
        {
          status: 429,
          headers: { 'Content-Type': 'application/problem+json', 'Retry-After': '125' },
        },
      ),
    );

    const error = await caught(apiSend('POST', '/alerts', BODY));

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 429,
      type: 'https://avisabus/problems/rate-limited',
      retryAfterS: 125,
    });
  });

  it.each([
    ['missing', null],
    ['an HTTP date', 'Wed, 04 Nov 2026 08:00:00 GMT'],
    ['negative', '-5'],
  ])('[passenger_alert_ui.AC-06] Retry-After %s gives null seconds', async (_, header) => {
    const headers = new Headers({ 'Content-Type': 'application/problem+json' });
    if (header !== null) headers.set('Retry-After', header);
    fetchMock.mockResolvedValue(new Response('{}', { status: 429, headers }));

    const error = await caught(apiSend('POST', '/alerts', BODY));

    expect(error).toMatchObject({ status: 429, retryAfterS: null });
  });

  it.each([
    [404, 'https://avisabus/problems/stop-not-found'],
    [422, 'https://avisabus/problems/bus-not-requestable'],
    [503, 'https://avisabus/problems/network-unavailable'],
  ])(
    '[passenger_alert_ui.AC-06] a problem+json %i is an ApiError with status and type',
    async (status, type) => {
      fetchMock.mockResolvedValue(problem(status, type));

      const error = await caught(apiSend('POST', '/alerts', BODY));

      expect(error).toBeInstanceOf(ApiError);
      expect(error).toMatchObject({ status, type, retryAfterS: null });
    },
  );

  it('[passenger_alert_ui.AC-06] a network error is an ApiError with status 0', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));

    const error = await caught(apiSend('DELETE', '/alerts/x'));

    expect(error).toMatchObject({ status: 0, type: 'network' });
  });

  it('[passenger_alert_ui.AC-06] gives up after 8 s with an ApiError with status 0', async () => {
    vi.useFakeTimers();
    vi.stubGlobal('fetch', hangingFetch());

    const result = caught(apiSend('POST', '/alerts', BODY));
    await vi.advanceTimersByTimeAsync(API_TIMEOUT_MS);

    expect(await result).toMatchObject({ status: 0, type: 'network' });
  });
});
