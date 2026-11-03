/** HTTP client of the AvisaBus API (passenger_stop_view design §3, AC-03). */

export const API_PREFIX = '/api/v1';
export const API_TIMEOUT_MS = 8_000;
export const NETWORK_ERROR_TYPE = 'network';

/**
 * Failed API call: `status` and `type` of the problem+json body, or status 0 and type
 * 'network' when there was no answer (network error or timeout).
 */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly type: string | null,
  ) {
    super(`API ${status}`);
    this.name = 'ApiError';
  }
}

function networkError(): ApiError {
  return new ApiError(0, NETWORK_ERROR_TYPE);
}

async function problemType(response: Response): Promise<string | null> {
  const contentType = response.headers.get('Content-Type') ?? '';
  if (!contentType.includes('application/problem+json')) return null;
  try {
    const body: unknown = await response.json();
    if (typeof body === 'object' && body !== null && 'type' in body) {
      return typeof body.type === 'string' ? body.type : null;
    }
  } catch {
    // Malformed problem body: only the status is known.
  }
  return null;
}

/**
 * GET `/api/v1${path}` and return its JSON body. Rejects with an ApiError for error responses,
 * network errors and requests without an answer after 8 s. If the caller aborts `signal`
 * (e.g. TanStack Query cancels the query), the abort error is passed through unchanged.
 */
export async function apiGet<T>(path: string, init: { signal?: AbortSignal } = {}): Promise<T> {
  const { signal } = init;
  const controller = new AbortController();
  const onAbort = () => controller.abort(signal?.reason);
  signal?.addEventListener('abort', onAbort, { once: true });
  if (signal?.aborted) onAbort();
  const timeout = setTimeout(() => controller.abort(), API_TIMEOUT_MS);

  try {
    let response: Response;
    try {
      response = await fetch(`${API_PREFIX}${path}`, {
        headers: { Accept: 'application/json' },
        signal: controller.signal,
      });
    } catch (error) {
      if (signal?.aborted) throw error;
      throw networkError();
    }
    if (!response.ok) {
      throw new ApiError(response.status, await problemType(response));
    }
    try {
      return (await response.json()) as T;
    } catch (error) {
      if (signal?.aborted) throw error;
      // The body could not be read or parsed: as if the answer never arrived.
      throw networkError();
    }
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener('abort', onAbort);
  }
}
