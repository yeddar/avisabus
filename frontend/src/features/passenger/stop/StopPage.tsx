import { useTranslation } from 'react-i18next';
import { useParams, useSearchParams } from 'react-router-dom';

import type { Arrival } from '../../../shared/api/types';
import { useServerNow } from '../../../shared/hooks/useServerNow';
import { useAnnounce } from '../../../shared/ui/Announcer';
import { Button } from '../../../shared/ui/Button';
import { RefreshIcon } from '../../../shared/ui/icons/RefreshIcon';
import { usePageTitle } from '../../../shared/ui/usePageTitle';
import { ArrivalsList } from './ArrivalsList';
import { SourceNotice } from './SourceNotice';
import { StopHeader } from './StopHeader';
import { formatUpdateTime } from './time';
import { useArrivingAnnouncements } from './useArrivingAnnouncements';
import { useStop, useStopArrivals } from './useStopQueries';
import { useUiLanguage } from './useUiLanguage';

/** Route /p/:stopId?t={token}: the passenger's stop view (CU-01). */
export function StopPage() {
  const { stopId = '' } = useParams();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('t') ?? '';
  return <StopView key={`${stopId}|${token}`} stopId={stopId} token={token} />;
}

/** Mounted only once there are data, so arrivals already "Llegando" on load are not announced. */
function ArrivingAnnouncer({ arrivals, now }: { arrivals: Arrival[]; now: Date }) {
  useArrivingAnnouncements(arrivals, now);
  return null;
}

function StopView({ stopId, token }: { stopId: string; token: string }) {
  const { t } = useTranslation();
  const language = useUiLanguage();
  const announce = useAnnounce();
  const stop = useStop(stopId, token);
  const arrivals = useStopArrivals(stopId, token);
  const now = useServerNow(arrivals.data?.generated_at);

  usePageTitle(stop.data?.name ?? t('stop.title'));

  async function refresh() {
    const result = await arrivals.refetch();
    if (!result.isError) announce(t('stop.refreshed'), 'polite');
  }

  return (
    <div className="flex flex-col gap-5">
      {stop.data === undefined ? (
        <h1 className="text-[1.75rem] leading-[1.15] font-bold">{t('stop.title')}</h1>
      ) : (
        <StopHeader stop={stop.data} />
      )}
      <section aria-labelledby="arrivals-h" className="flex flex-col gap-3">
        <h2 id="arrivals-h" className="text-[1.375rem] font-bold">
          {t('stop.arrivals')}
        </h2>
        {arrivals.data === undefined ? (
          <p className="text-text-muted">{t('stop.loading')}</p>
        ) : (
          <>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="text-text-muted">
                {t('stop.updatedAt', {
                  time: formatUpdateTime(arrivals.data.generated_at, language),
                })}
              </p>
              <Button icon={<RefreshIcon className="size-[18px]" />} onClick={() => void refresh()}>
                {t('stop.refresh')}
              </Button>
            </div>
            <ArrivingAnnouncer arrivals={arrivals.data.arrivals} now={now} />
            <SourceNotice source={arrivals.data.source} />
            <ArrivalsList
              arrivals={arrivals.data.arrivals}
              source={arrivals.data.source}
              now={now}
            />
          </>
        )}
      </section>
    </div>
  );
}
