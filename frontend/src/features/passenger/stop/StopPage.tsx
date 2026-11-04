import type { UseQueryResult } from '@tanstack/react-query';
import {
  type ReactNode,
  type RefObject,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { useParams, useSearchParams } from 'react-router-dom';

import type { ApiError } from '../../../shared/api/client';
import type { Arrival, StopArrivalsResponse, StopResponse } from '../../../shared/api/types';
import { useOnline } from '../../../shared/hooks/useOnline';
import { useServerNow } from '../../../shared/hooks/useServerNow';
import { formatClockTime } from '../../../shared/i18n/format';
import { useAnnounce } from '../../../shared/ui/Announcer';
import { Button } from '../../../shared/ui/Button';
import { RefreshIcon } from '../../../shared/ui/icons/RefreshIcon';
import { StatusNotice } from '../../../shared/ui/StatusNotice';
import { usePageTitle } from '../../../shared/ui/usePageTitle';
import { ArrivalsList } from './ArrivalsList';
import { SourceNotice } from './SourceNotice';
import { StopHeader } from './StopHeader';
import { StopNotFound } from './StopNotFound';
import { setLastStop } from './lastStop';
import { formatUpdateTime } from './time';
import { useArrivingAnnouncements } from './useArrivingAnnouncements';
import { isNotFound, useStop, useStopArrivals } from './useStopQueries';
import { useUiLanguage } from './useUiLanguage';

const H1 = 'text-[1.75rem] leading-[1.15] font-bold';

/** Requests the person made with "Actualizar" or "Reintentar" (passenger_stop_view.AC-24). */
type ManualAction = 'refresh' | 'retry';
/**
 * Control that gets the focus; a new object per request. `lost`: the focused "Reintentar"
 * disappeared, so the focus moves only while nothing else has taken it (it is on body).
 */
type FocusRequest = { target: ManualAction; lost?: boolean };

const isFailure = (result: { isError: boolean }) => result.isError;
const isNotFoundResult = (result: { error: ApiError | null }) => isNotFound(result.error);

/**
 * A query without data that failed and is being asked again: TanStack Query v5 puts it back to
 * "pending" (without error) while the request is in flight or paused without connection.
 */
const isRetryingAfterError = (result: UseQueryResult<unknown, ApiError>) =>
  result.isPending && result.fetchStatus !== 'idle' && result.errorUpdateCount > 0;

/** Route /p/:stopId?t={token}: the passenger's stop view (CU-01). */
export function StopPage() {
  const { stopId = '' } = useParams();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('t');
  // Without a token the API would answer 404 anyway: do not call it (design §3).
  if (token === null || token === '') return <StopNotFound />;
  return <StopView key={`${stopId}|${token}`} stopId={stopId} token={token} />;
}

function StopView({ stopId, token }: { stopId: string; token: string }) {
  const stop = useStop(stopId, token);
  const arrivals = useStopArrivals(stopId, token);
  // A manual action answered with a 404 takes the focus to the h1 (passenger_stop_view.AC-24).
  const [manualNotFound, setManualNotFound] = useState(false);
  const onManualNotFound = useCallback(() => setManualNotFound(true), []);

  if (isNotFound(stop.error) || isNotFound(arrivals.error)) {
    return <StopNotFound focusHeading={manualNotFound} />;
  }
  return (
    <StopContent
      stop={stop}
      arrivals={arrivals}
      stopId={stopId}
      token={token}
      onManualNotFound={onManualNotFound}
    />
  );
}

interface RetryActionProps {
  control: RefObject<HTMLDivElement | null>;
  /** Called when the button is removed while it has the focus. */
  onRemovedWithFocus: () => void;
  children: ReactNode;
}

/** Wrapper of "Reintentar" that notices when it disappears with the focus on it. */
function RetryAction({ control, onRemovedWithFocus, children }: RetryActionProps) {
  useLayoutEffect(() => {
    const element = control.current;
    // Layout cleanups of a removed subtree run before its nodes leave the DOM (like
    // componentWillUnmount), so the focus can still be read here.
    return () => {
      if (element?.contains(document.activeElement)) onRemovedWithFocus();
    };
  }, [control, onRemovedWithFocus]);

  return (
    <div ref={control} className="flex">
      {children}
    </div>
  );
}

/** Mounted only once there are data, so arrivals already "Llegando" on load are not announced. */
function ArrivingAnnouncer({ arrivals, now }: { arrivals: Arrival[]; now: Date }) {
  useArrivingAnnouncements(arrivals, now);
  return null;
}

interface StopContentProps {
  stop: UseQueryResult<StopResponse, ApiError>;
  arrivals: UseQueryResult<StopArrivalsResponse, ApiError>;
  stopId: string;
  token: string;
  /** A manual action ended with a 404: the view becomes "Parada no encontrada". */
  onManualNotFound: () => void;
}

function StopContent({ stop, arrivals, stopId, token, onManualNotFound }: StopContentProps) {
  const { t } = useTranslation();
  const language = useUiLanguage();
  const announce = useAnnounce();
  const online = useOnline();
  const now = useServerNow(arrivals.data?.generated_at);
  const failed = stop.isError || arrivals.isError;
  const data = arrivals.data;
  const [manualAction, setManualAction] = useState<ManualAction | null>(null);
  const [focusRequest, setFocusRequest] = useState<FocusRequest | null>(null);
  const focusDone = useRef<FocusRequest | null>(null);
  const refreshControl = useRef<HTMLDivElement>(null);
  const retryControl = useRef<HTMLDivElement>(null);
  // While a retry (manual or automatic) is in flight the queries without data go back to
  // "pending": keep the error notice so that "Reintentar" (and the focus on it) does not
  // disappear meanwhile. It goes away when the data arrive (passenger_stop_view.AC-24).
  const showError =
    failed ||
    manualAction === 'retry' ||
    isRetryingAfterError(stop) ||
    isRetryingAfterError(arrivals);
  const showRefresh = data !== undefined && !arrivals.isError;

  usePageTitle(stop.data?.name ?? t('stop.title'));

  // Offered on the home page as "Tu última parada" (passenger_stop_view.AC-19).
  const loaded = stop.data;
  useEffect(() => {
    if (loaded !== undefined) setLastStop({ stopId: loaded.stop_id, name: loaded.name, token });
  }, [loaded, token]);

  // The control that must receive the focus may only appear once the new state is painted.
  useEffect(() => {
    if (focusRequest === null || focusDone.current === focusRequest) return;
    // Never take the focus from wherever the person has put it meanwhile.
    const focusMoved = document.activeElement !== null && document.activeElement !== document.body;
    if (focusRequest.lost === true && focusMoved) {
      focusDone.current = focusRequest;
      return;
    }
    const control = focusRequest.target === 'retry' ? retryControl : refreshControl;
    const button = control.current?.querySelector('button');
    if (button == null) return;
    button.focus();
    focusDone.current = focusRequest;
  }, [focusRequest, showError, showRefresh]);

  // "Reintentar" had the focus and an automatic refresh made it disappear: go to "Actualizar",
  // without announcement (passenger_stop_view.AC-24, AC-15). Also harmless after a manual one.
  const onRetryRemovedWithFocus = useCallback(
    () => setFocusRequest({ target: 'refresh', lost: true }),
    [],
  );

  /**
   * End of a manual action (passenger_stop_view.AC-14, AC-24): polite announcement and focus on
   * a visible control. Automatic refreshes never get here, so they stay silent (AC-15).
   */
  function finish(action: ManualAction, failedNow: boolean) {
    setManualAction(null);
    announce(t(failedNow ? 'stop.refreshFailed' : 'stop.refreshed'), 'polite');
    // "Actualizar" that fails is replaced by the stale data text: go to "Reintentar". A
    // successful "Reintentar" removes the error notice: go to "Actualizar". Otherwise the
    // focused control is still there.
    if (action === 'refresh' && failedNow) setFocusRequest({ target: 'retry' });
    if (action === 'retry' && !failedNow) setFocusRequest({ target: 'refresh' });
  }

  async function refresh() {
    if (manualAction !== null) return;
    setManualAction('refresh');
    const result = await arrivals.refetch();
    // The view becomes "Parada no encontrada", whose h1 is read when it gets the focus.
    if (isNotFoundResult(result)) return onManualNotFound();
    finish('refresh', result.isError);
  }

  /** Asks again for the arrivals and, if it failed, for the stop (passenger_stop_view.AC-17). */
  async function retry() {
    if (manualAction !== null) return;
    setManualAction('retry');
    const results = await Promise.all([
      arrivals.refetch(),
      ...(stop.isError ? [stop.refetch()] : []),
    ]);
    if (results.some(isNotFoundResult)) return onManualNotFound();
    finish('retry', results.some(isFailure));
  }

  return (
    <div className="flex flex-col gap-5">
      {stop.data === undefined ? (
        <h1 className={H1}>{t('stop.title')}</h1>
      ) : (
        <StopHeader stop={stop.data} />
      )}
      <section aria-labelledby="arrivals-h" className="flex flex-col gap-3">
        <h2 id="arrivals-h" className="text-[1.375rem] font-bold">
          {t('stop.arrivals')}
        </h2>
        {!online && (
          <StatusNotice role="status">
            <Trans i18nKey="network.offline" components={{ strong: <strong /> }} />
          </StatusNotice>
        )}
        {showError && (
          <StatusNotice
            action={
              <RetryAction control={retryControl} onRemovedWithFocus={onRetryRemovedWithFocus}>
                <Button icon={<RefreshIcon className="size-[18px]" />} onClick={() => void retry()}>
                  {t('stop.error.retry')}
                </Button>
              </RetryAction>
            }
          >
            <Trans i18nKey="stop.error.body" components={{ strong: <strong /> }} />
          </StatusNotice>
        )}
        {data === undefined ? (
          !showError && online && <p className="text-text-muted">{t('stop.loading')}</p>
        ) : (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3">
              {arrivals.isError ? (
                <p className="font-bold text-text">
                  {t('stop.stale', { time: formatClockTime(data.generated_at, language) })}
                </p>
              ) : (
                <>
                  <p className="text-text-muted">
                    {t('stop.updatedAt', { time: formatUpdateTime(data.generated_at, language) })}
                  </p>
                  <div ref={refreshControl} className="flex">
                    <Button
                      icon={<RefreshIcon className="size-[18px]" />}
                      onClick={() => void refresh()}
                    >
                      {t('stop.refresh')}
                    </Button>
                  </div>
                </>
              )}
            </div>
            <ArrivingAnnouncer arrivals={data.arrivals} now={now} />
            <SourceNotice source={data.source} />
            <ArrivalsList
              arrivals={data.arrivals}
              source={data.source}
              now={now}
              stopId={stopId}
              token={token}
            />
          </>
        )}
      </section>
    </div>
  );
}
