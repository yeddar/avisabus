import { useEffect, useMemo, useRef, useState } from 'react';
import { Trans, useTranslation } from 'react-i18next';
import { Link, useParams, useSearchParams } from 'react-router-dom';

import type { PositionResponse, ShapeResponse } from '../../../shared/api/types';
import { useOnline } from '../../../shared/hooks/useOnline';
import { useServerNow } from '../../../shared/hooks/useServerNow';
import { formatClockTime } from '../../../shared/i18n/format';
import { useAnnounce } from '../../../shared/ui/Announcer';
import { Button } from '../../../shared/ui/Button';
import { ArrowLeftIcon } from '../../../shared/ui/icons/ArrowLeftIcon';
import { RefreshIcon } from '../../../shared/ui/icons/RefreshIcon';
import { StatusNotice } from '../../../shared/ui/StatusNotice';
import { usePageTitle } from '../../../shared/ui/usePageTitle';
import { isNotFound } from '../stop/useStopQueries';
import { gtfsLang, useUiLanguage } from '../stop/useUiLanguage';
import { BusMap } from './BusMap';
import { buildMapModel } from './mapModel';
import { PositionSummary } from './PositionSummary';
import { buildSummary, summaryPlainText } from './summary';
import { usePosition, useShape } from './usePositionQueries';
import { useProximityAnnouncements } from './useProximityAnnouncements';

const H1 = 'text-[1.375rem] leading-[1.2] font-bold';
const SUMMARY_TEXT_ID = 'map-summary-text';
const DIRECTION = /^\d+$/;

function stopPath(stopId: string, token: string | null): string {
  const query = token === null || token === '' ? '' : `?t=${encodeURIComponent(token)}`;
  return `/p/${encodeURIComponent(stopId)}${query}`;
}

/** "Volver a la parada": link with a back arrow, 44 px high (docs/design.md §5.7). */
function BackLink({ stopId, token }: { stopId: string; token: string | null }) {
  const { t } = useTranslation();
  return (
    <Link
      to={stopPath(stopId, token)}
      className="inline-flex min-h-11 items-center gap-2 self-start font-bold text-accent underline underline-offset-4 hover:text-accent-hover"
    >
      <ArrowLeftIcon className="size-5 shrink-0" />
      {t('map.back')}
    </Link>
  );
}

/** Line and direction not found at the stop, or an unusable URL (passenger_map_view.AC-13). */
function LineNotFound({ stopId, token }: { stopId: string; token: string | null }) {
  const { t } = useTranslation();
  usePageTitle(t('map.notFound'));
  return (
    <div className="flex flex-col gap-5">
      <h1 className={H1}>{t('map.notFound')}</h1>
      <BackLink stopId={stopId} token={token} />
    </div>
  );
}

/**
 * Route /p/:stopId/map/:line/:directionId?t={token}, loaded on demand (passenger_map_view,
 * CU-02). Without a token or with a direction that is not an integer ≥ 0, the API is not called.
 */
export function MapPage() {
  const { stopId = '', line = '', directionId = '' } = useParams();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('t');
  if (token === null || token === '' || !DIRECTION.test(directionId)) {
    return <LineNotFound stopId={stopId} token={token} />;
  }
  return (
    <MapView
      key={`${stopId}|${line}|${directionId}|${token}`}
      stopId={stopId}
      line={line}
      directionId={Number(directionId)}
      token={token}
    />
  );
}

interface MapViewProps {
  stopId: string;
  line: string;
  directionId: number;
  token: string;
}

/** First stop of the shape, for the NOT_STARTED summary (AC-04); null without the shape. */
function firstStopOf(shape: ShapeResponse | undefined): string | null {
  if (shape === undefined) return null;
  const [first] = [...shape.stops].sort((a, b) => a.sequence - b.sequence);
  return first?.name ?? null;
}

function MapView({ stopId, line, directionId, token }: MapViewProps) {
  const position = usePosition(stopId, token, line, directionId);
  if (isNotFound(position.error)) return <LineNotFound stopId={stopId} token={token} />;
  return <MapContent stopId={stopId} line={line} token={token} position={position} />;
}

/** Mounted with the first data, so what they already show is not announced (AC-06). */
function ProximityAnnouncer({ position }: { position: PositionResponse }) {
  useProximityAnnouncements(position);
  return null;
}

interface MapContentProps {
  stopId: string;
  line: string;
  token: string;
  position: ReturnType<typeof usePosition>;
}

function MapContent({ stopId, line, token, position }: MapContentProps) {
  const { t } = useTranslation();
  const language = useUiLanguage();
  const announce = useAnnounce();
  const online = useOnline();
  const data = position.data;
  const shapeId = data?.shape_id ?? null;
  const shape = useShape(shapeId);
  const now = useServerNow(data?.generated_at);
  const [retrying, setRetrying] = useState(false);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const retryControl = useRef<HTMLDivElement>(null);
  const focusHeading = useRef(false);

  // A missing shape is not an error: the map shows the stop and the bus (AC-07).
  const shapeFailed = shape.isError && !isNotFound(shape.error);
  const failed = position.isError || shapeFailed;
  // Keep the notice (and the focus on "Reintentar") while a retry is in flight.
  const showError = failed || retrying;

  const destination = data === undefined ? null : (data.arrival?.destination ?? data.headsign);
  const titleText =
    destination === null
      ? t('stop.lineName', { line })
      : summaryPlainText(
          t('map.title', { line, destination }).replace(/<(\/?)destination>/g, '<$1name>'),
        );
  usePageTitle(titleText);

  const shapeData = shape.data ?? null;
  const model = useMemo(
    () => (data === undefined ? null : buildMapModel(shapeData, data)),
    [shapeData, data],
  );
  // Frame once the final bounds are known (AC-08): with a position they do not depend on the
  // shape; without it, wait for the shape (or for its absence).
  const ready =
    data !== undefined &&
    (data.position !== null || shapeId === null || shape.isSuccess || shape.isError);

  // After a successful "Reintentar" its button disappears: the focus goes to the h1.
  useEffect(() => {
    if (!showError && focusHeading.current) {
      focusHeading.current = false;
      const heading = headingRef.current;
      if (heading !== null) {
        heading.tabIndex = -1;
        heading.focus();
      }
    }
  }, [showError]);

  /** Asks again for what failed; the result is announced, like in the stop view. */
  async function retry() {
    if (retrying) return;
    setRetrying(true);
    const results = await Promise.all([
      ...(position.isError ? [position.refetch()] : []),
      ...(shapeFailed ? [shape.refetch()] : []),
    ]);
    const failedNow = results.some((result) => result.isError);
    const hadFocus = retryControl.current?.contains(document.activeElement) ?? false;
    focusHeading.current = !failedNow && hadFocus;
    setRetrying(false);
    announce(t(failedNow ? 'stop.refreshFailed' : 'stop.refreshed'), 'polite');
  }

  return (
    <div className="flex flex-col gap-5">
      <BackLink stopId={stopId} token={token} />
      <h1 ref={headingRef} className={H1}>
        {destination === null ? (
          t('stop.lineName', { line })
        ) : (
          <Trans
            i18nKey="map.title"
            values={{ line, destination }}
            components={{ destination: <span lang={gtfsLang(language)} /> }}
          />
        )}
      </h1>
      {!online && (
        <StatusNotice role="status">
          <Trans i18nKey="network.offline" components={{ strong: <strong /> }} />
        </StatusNotice>
      )}
      {showError && (
        <StatusNotice
          action={
            <div ref={retryControl} className="flex">
              <Button icon={<RefreshIcon className="size-[18px]" />} onClick={() => void retry()}>
                {t('stop.error.retry')}
              </Button>
            </div>
          }
        >
          <Trans i18nKey="stop.error.body" components={{ strong: <strong /> }} />
        </StatusNotice>
      )}
      {data === undefined || model === null ? (
        !showError && online && <p className="text-lg text-text-muted">{t('map.loading')}</p>
      ) : (
        <>
          {position.isError && (
            <p className="font-bold text-text">
              {t('stop.stale', { time: formatClockTime(data.generated_at, language) })}
            </p>
          )}
          <ProximityAnnouncer position={data} />
          <PositionSummary
            summary={buildSummary(data, firstStopOf(shape.data), t, language, now)}
            textId={SUMMARY_TEXT_ID}
          />
          <BusMap model={model} ready={ready} />
        </>
      )}
    </div>
  );
}
