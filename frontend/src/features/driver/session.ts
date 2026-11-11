/**
 * Session of the driver: the token lives only in sessionStorage (driver_ui.AC-01, conventions §4)
 * and every call to the driver API carries it as a bearer token.
 */
import { API_PREFIX, API_TIMEOUT_MS, ApiError, NETWORK_ERROR_TYPE } from '../../shared/api/client';

const TOKEN_KEY = 'avisabus.driverSession';
const UNAUTHORIZED = 401;
const NO_CONTENT = 204;

/** The API answered 401: the token is not (or no longer) valid (driver_ui.AC-03). */
export class DriverAuthError extends Error {
  constructor() {
    super('Driver session is not valid');
    this.name = 'DriverAuthError';
  }
}

/** Reading or writing sessionStorage can throw (disabled storage): degrade to "no token". */
export function getDriverToken(): string | null {
  try {
    return window.sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setDriverToken(token: string): void {
  try {
    window.sessionStorage.setItem(TOKEN_KEY, token);
  } catch {
    // Storage unavailable: the next call will be rejected and the driver asked for the code.
  }
}

export function clearDriverToken(): void {
  try {
    window.sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    // Storage unavailable: there is nothing stored to remove.
  }
}

type AuthLostListener = () => void;
const authLostListeners = new Set<AuthLostListener>();

/** Calls `listener` whenever the session is lost; the pages navigate to /driver (AC-03). */
export function subscribeDriverAuthLost(listener: AuthLostListener): () => void {
  authLostListeners.add(listener);
  return () => {
    authLostListeners.delete(listener);
  };
}

/** Forgets the token and tells the pages: a 401 of the API or the close 4401 of the socket. */
export function loseDriverAuth(): void {
  clearDriverToken();
  authLostListeners.forEach((listener) => listener());
}

export interface DriverApiResult<T> {
  status: number;
  /** JSON body of a successful response; null for 204 and for error responses. */
  data: T | null;
  /** Seconds of the Retry-After header of a 429; null otherwise. */
  retryAfterS: number | null;
}

function retryAfterSeconds(response: Response): number | null {
  const value = response.headers.get('Retry-After')?.trim() ?? '';
  return /^\d+$/.test(value) ? Number(value) : null;
}

/**
 * Calls `/api/v1${path}` with the bearer token of the shift. Every HTTP answer is returned except
 * a 401, which clears the token and rejects with DriverAuthError (AC-03); a network error or a
 * request without an answer after 8 s rejects with an ApiError of status 0.
 */
export async function driverApi<T>(
  method: 'GET' | 'POST' | 'PUT' | 'DELETE',
  path: string,
  body?: unknown,
): Promise<DriverApiResult<T>> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  const token = getDriverToken();
  if (token !== null) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers['Content-Type'] = 'application/json';

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), API_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_PREFIX}${path}`, {
      method,
      headers,
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      signal: controller.signal,
    });
    if (response.status === UNAUTHORIZED) {
      loseDriverAuth();
      throw new DriverAuthError();
    }
    const retryAfterS = retryAfterSeconds(response);
    if (!response.ok || response.status === NO_CONTENT) {
      return { status: response.status, data: null, retryAfterS };
    }
    const text = await response.text();
    return {
      status: response.status,
      data: text === '' ? null : (JSON.parse(text) as T),
      retryAfterS,
    };
  } catch (error) {
    if (error instanceof DriverAuthError) throw error;
    throw new ApiError(0, NETWORK_ERROR_TYPE);
  } finally {
    clearTimeout(timeout);
  }
}
