import type { UseQueryResult } from '@tanstack/react-query';
import { useEffect } from 'react';
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

  if (isNotFound(stop.error) || isNotFound(arrivals.error)) return <StopNotFound />;
  return <StopContent stop={stop} arrivals={arrivals} token={token} />;
}

/** Mounted only once there are data, so arrivals already "Llegando" on load are not announced. */
function ArrivingAnnouncer({ arrivals, now }: { arrivals: Arrival[]; now: Date }) {
  useArrivingAnnouncements(arrivals, now);
  return null;
}

interface StopContentProps {
  stop: UseQueryResult<StopResponse, ApiError>;
  arrivals: UseQueryResult<StopArrivalsResponse, ApiError>;
  token: string;
}

function StopContent({ stop, arrivals, token }: StopContentProps) {
  const { t } = useTranslation();
  const language = useUiLanguage();
  const announce = useAnnounce();
  const online = useOnline();
  const now = useServerNow(arrivals.data?.generated_at);
  const failed = stop.isError || arrivals.isError;
  const data = arrivals.data;

  usePageTitle(stop.data?.name ?? t('stop.title'));

  // Offered on the home page as "Tu última parada" (passenger_stop_view.AC-19).
  const loaded = stop.data;
  useEffect(() => {
    if (loaded !== undefined) setLastStop({ stopId: loaded.stop_id, name: loaded.name, token });
  }, [loaded, token]);

  async function refresh() {
    const result = await arrivals.refetch();
    if (!result.isError) announce(t('stop.refreshed'), 'polite');
  }

  function retry() {
    if (stop.isError) void stop.refetch();
    void arrivals.refetch();
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
        {failed && (
          <StatusNotice
            action={
              <Button icon={<RefreshIcon className="size-[18px]" />} onClick={retry}>
                {t('stop.error.retry')}
              </Button>
            }
          >
            <Trans i18nKey="stop.error.body" components={{ strong: <strong /> }} />
          </StatusNotice>
        )}
        {data === undefined ? (
          !failed && online && <p className="text-text-muted">{t('stop.loading')}</p>
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
                  <Button
                    icon={<RefreshIcon className="size-[18px]" />}
                    onClick={() => void refresh()}
                  >
                    {t('stop.refresh')}
                  </Button>
                </>
              )}
            </div>
            <ArrivingAnnouncer arrivals={data.arrivals} now={now} />
            <SourceNotice source={data.source} />
            <ArrivalsList arrivals={data.arrivals} source={data.source} now={now} />
          </>
        )}
      </section>
    </div>
  );
}
