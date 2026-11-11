import { type FormEvent, useEffect, useRef, useState } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';

import { useAnnounce } from '../../shared/ui/Announcer';
import { Button } from '../../shared/ui/Button';
import { StatusNotice } from '../../shared/ui/StatusNotice';
import { usePageTitle } from '../../shared/ui/usePageTitle';
import { DriverAuthError, driverApi, setDriverToken } from './session';

const CODE_DIGITS = 8;
const GROUP = 4;
const SECONDS_PER_MINUTE = 60;
const CREATED = 201;
const TOO_MANY_REQUESTS = 429;
/** Minutes shown with a 429 that has no usable Retry-After: the block of driver_session.AC-02. */
const LOCK_FALLBACK_MIN = 15;

type LoginError = { kind: 'invalid' } | { kind: 'locked'; minutes: number } | { kind: 'failed' };

type ClosedReason = 'ENDED' | 'IDLE' | 'REVOKED' | 'REPLACED';

/** Keeps at most 8 digits and groups them as "1234 5678". */
function formatCode(raw: string): string {
  const digits = raw.replace(/\D/g, '').slice(0, CODE_DIGITS);
  return digits.length > GROUP ? `${digits.slice(0, GROUP)} ${digits.slice(GROUP)}` : digits;
}

function lockMinutes(retryAfterS: number | null): number {
  return retryAfterS === null
    ? LOCK_FALLBACK_MIN
    : Math.max(1, Math.ceil(retryAfterS / SECONDS_PER_MINUTE));
}

/** /driver: asks for the access code (driver_ui.AC-01) and shows why a shift ended (AC-10). */
export function LoginPage() {
  const { t } = useTranslation();
  usePageTitle(t('driver.login.title'));
  const announce = useAnnounce();
  const navigate = useNavigate();
  const location = useLocation();
  const closedReason = (location.state as { closedReason?: ClosedReason } | null)?.closedReason;
  const closedMessage = closedReason === undefined ? null : t(`driver.closed.${closedReason}`);
  const [code, setCode] = useState('');
  const [error, setError] = useState<LoginError | null>(null);
  const sending = useRef(false);
  const errorMessage = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    if (closedMessage !== null) announce(closedMessage);
  }, [announce, closedMessage]);

  useEffect(() => {
    if (error !== null) errorMessage.current?.focus();
  }, [error]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (sending.current) return;
    sending.current = true;
    setError(null);
    try {
      const result = await driverApi<{ session_token: string }>('POST', '/driver/sessions', {
        code: code.replace(/\s/g, ''),
      });
      if (result.status === CREATED && result.data !== null) {
        setDriverToken(result.data.session_token);
        void navigate('/driver/shift', { replace: true });
        return;
      }
      setError(
        result.status === TOO_MANY_REQUESTS
          ? { kind: 'locked', minutes: lockMinutes(result.retryAfterS) }
          : { kind: 'failed' },
      );
    } catch (failure) {
      setError(failure instanceof DriverAuthError ? { kind: 'invalid' } : { kind: 'failed' });
    } finally {
      sending.current = false;
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-[560px] flex-col gap-5">
      <h1 className="text-[1.75rem] leading-[1.15] font-bold">{t('driver.login.title')}</h1>
      {closedMessage !== null && <StatusNotice>{closedMessage}</StatusNotice>}
      <form onSubmit={(event) => void submit(event)} className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <label htmlFor="driver-code" className="text-lg font-bold">
            {t('driver.login.code')}
          </label>
          <input
            id="driver-code"
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            required
            value={code}
            onChange={(event) => setCode(formatCode(event.target.value))}
            className="min-h-16 w-full rounded-[10px] border-2 border-control-border px-3 text-center text-[2.5rem] leading-none font-bold tracking-[0.12em] tabular-nums"
          />
        </div>
        {error !== null && (
          <p
            ref={errorMessage}
            role="alert"
            tabIndex={-1}
            className="rounded-[10px] border-2 border-occ-full-fg bg-occ-full-bg p-3 font-bold text-occ-full-fg"
          >
            {error.kind === 'invalid' && t('driver.login.invalid')}
            {error.kind === 'locked' && t('driver.login.locked', { count: error.minutes })}
            {error.kind === 'failed' && (
              <Trans i18nKey="stop.error.body" components={{ strong: <strong /> }} />
            )}
          </p>
        )}
        <Button type="submit" variant="primary" className="min-h-16 w-full text-xl">
          {t('driver.login.enter')}
        </Button>
      </form>
    </div>
  );
}
