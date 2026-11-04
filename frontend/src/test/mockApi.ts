import { vi } from 'vitest';

/** Minimal Response used by the fake fetch (synchronous body, no streams or real timers). */
export interface FakeReply {
  status: number;
  body: unknown;
  /** Extra response headers (e.g. Retry-After). */
  headers?: Record<string, string>;
}

export const ok = (body: unknown): FakeReply => ({ status: 200, body });

export const problem = (status: number, type: string): FakeReply => ({
  status,
  body: { type, title: 'Error', status },
});

export const STOP_NOT_FOUND = 'https://avisabus/problems/stop-not-found';
export const NETWORK_UNAVAILABLE = 'https://avisabus/problems/network-unavailable';

/** Thrown by a handler to simulate a network error (fetch rejects). */
export class NetworkFailure extends Error {}

type Handler = (url: URL, init?: RequestInit) => FakeReply | Promise<FakeReply>;

function toResponse({ status, body, headers = {} }: FakeReply): Response {
  const contentType = status < 400 ? 'application/json' : 'application/problem+json';
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: new Headers({ 'Content-Type': contentType, ...headers }),
    json: () => Promise.resolve(structuredClone(body)),
    text: () => Promise.resolve(body === null ? '' : JSON.stringify(body)),
  } as Response;
}

/**
 * Replaces the global fetch with a fake API: `handler` receives the requested URL and returns
 * the reply (or a promise of it, to keep a request pending). No network is ever used.
 */
export function mockApi(handler: Handler) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), 'http://localhost');
    const signal = init?.signal;
    const reply = Promise.resolve().then(() => handler(url, init));
    const aborted = new Promise<never>((_resolve, reject) => {
      signal?.addEventListener('abort', () =>
        reject(new DOMException('The operation was aborted.', 'AbortError')),
      );
    });
    try {
      return toResponse(await Promise.race([reply, aborted]));
    } catch (error) {
      if (error instanceof NetworkFailure) throw new TypeError('Failed to fetch');
      throw error;
    }
  });
  vi.stubGlobal('fetch', fetchMock);

  return {
    fetchMock,
    calls: (fragment: string) =>
      fetchMock.mock.calls.filter(([input]) => String(input).includes(fragment)).length,
    arrivalCalls: () =>
      fetchMock.mock.calls.filter(([input]) => /\/stops\/[^/?]+\/arrivals/.test(String(input)))
        .length,
  };
}

/** Promise that the test resolves when it wants (e.g. to observe a request in flight). */
export function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

/** Sets document.visibilityState and fires visibilitychange (TanStack Query listens to it). */
export function setVisibility(state: 'visible' | 'hidden') {
  Object.defineProperty(document, 'visibilityState', { configurable: true, get: () => state });
  document.dispatchEvent(new Event('visibilitychange', { bubbles: true }));
}
