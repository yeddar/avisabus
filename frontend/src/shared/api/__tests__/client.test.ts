import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { API_TIMEOUT_MS, ApiError, apiGet } from '../client';
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
