/** HTTP client of the AvisaBus API (passenger_stop_view design §3, AC-03). */
import { getDeviceId } from '../device/deviceId';

export const API_PREFIX = '/api/v1';
export const API_TIMEOUT_MS = 8_000;
export const NETWORK_ERROR_TYPE = 'network';

/**
 * Failed API call: `status` and `type` of the problem+json body, or status 0 and type
 * 'network' when there was no answer (network error or timeout). `retryAfterS`: seconds of the
 * Retry-After header of a 429 (passenger_alert_ui.AC-06), null otherwise or if it is not a
 * number of seconds.
 */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly type: string | null,
    readonly retryAfterS: number | null = null,
  ) {
    super(`API ${status}`);
    this.name = 'ApiError';
  }
}

const TOO_MANY_REQUESTS = 429;
const NO_CONTENT = 204;

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

/** Retry-After as a number of seconds; an HTTP date or anything else gives null. */
function retryAfterSeconds(response: Response): number | null {
  const value = response.headers.get('Retry-After')?.trim() ?? '';
  return /^\d+$/.test(value) ? Number(value) : null;
}

type Method = 'GET' | 'POST' | 'DELETE';

interface RequestOptions {
  headers: Record<string, string>;
  body?: string;
  signal?: AbortSignal;
}

/**
 * Runs `fetch` for `/api/v1${path}` and reads the body with `read`. Rejects with an ApiError for
 * error responses, network errors and requests without an answer after 8 s. If the caller
 * aborts `signal`, the abort error is passed through unchanged.
 */
async function request<T>(
  method: Method,
  path: string,
  { headers, body, signal }: RequestOptions,
  read: (response: Response) => Promise<T>,
): Promise<T> {
  const controller = new AbortController();
  const onAbort = () => controller.abort(signal?.reason);
  signal?.addEventListener('abort', onAbort, { once: true });
  if (signal?.aborted) onAbort();
  const timeout = setTimeout(() => controller.abort(), API_TIMEOUT_MS);

  try {
    let response: Response;
    try {
      response = await fetch(`${API_PREFIX}${path}`, {
        ...(method === 'GET' ? {} : { method }),
        headers,
        ...(body === undefined ? {} : { body }),
        signal: controller.signal,
      });
    } catch (error) {
      if (signal?.aborted) throw error;
      throw networkError();
    }
    if (!response.ok) {
      const retryAfterS =
        response.status === TOO_MANY_REQUESTS ? retryAfterSeconds(response) : null;
      throw new ApiError(response.status, await problemType(response), retryAfterS);
    }
    try {
      return await read(response);
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

/**
 * GET `/api/v1${path}` and return its JSON body. Rejects with an ApiError for error responses,
 * network errors and requests without an answer after 8 s. If the caller aborts `signal`
 * (e.g. TanStack Query cancels the query), the abort error is passed through unchanged.
 */
export async function apiGet<T>(path: string, init: { signal?: AbortSignal } = {}): Promise<T> {
  return request(
    'GET',
    path,
    { headers: { Accept: 'application/json' }, signal: init.signal },
    async (response) => (await response.json()) as T,
  );
}

export interface ApiSendResult<T> {
  status: number;
  /** JSON body; null for 204 or an empty body. */
  data: T | null;
  retryAfterS: number | null;
}

/**
 * Request on behalf of this device (passenger_alert_ui design §3): adds X-Device-Id, the only
 * place where the identifier travels over HTTP (AC-01), and a JSON Content-Type when there is
 * a body. Same errors as apiGet; a 429 carries the Retry-After seconds in `retryAfterS`.
 * Used for POST/DELETE /alerts and for GET /alerts/mine, which also needs the header.
 */
export async function apiSend<T>(
  method: Method,
  path: string,
  body?: unknown,
  init: { signal?: AbortSignal } = {},
): Promise<ApiSendResult<T>> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
    'X-Device-Id': getDeviceId(),
  };
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  return request(
    method,
    path,
    {
      headers,
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      signal: init.signal,
    },
    async (response) => {
      const text = response.status === NO_CONTENT ? '' : await response.text();
      return {
        status: response.status,
        data: text === '' ? null : (JSON.parse(text) as T),
        retryAfterS: retryAfterSeconds(response),
      };
    },
  );
}
