import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { safeStorage } from '../../shared/device/storage';
import { formatClockTime } from '../../shared/i18n/format';
import { GtfsText } from '../../shared/i18n/GtfsText';
import { Button } from '../../shared/ui/Button';
import { CheckIcon } from '../../shared/ui/icons/CheckIcon';
import { LineBadge } from '../passenger/stop/LineBadge';
import { useUiLanguage } from '../passenger/stop/useUiLanguage';
import { CapacityBanner } from './CapacityBanner';
import { DriverStatus } from './DriverStatus';
import { EndShiftDialog } from './EndShiftDialog';
import { BellIcon } from './icons/BellIcon';
import { WarningIcon } from './icons/WarningIcon';
import { diffAlerts } from './newAlerts';
import { clearDriverToken, driverApi } from './session';
import { StopCard } from './StopCard';
import { playTone } from './tone';
import type { DriverService, DriverView } from './types';
import type { SessionCloseReason } from './useDriverSocket';
import type { DriverShift, DriverViewListener } from './useDriverShift';

const MUTE_KEY = 'avisabus.driverMute';
const HIGHLIGHT_MS = 10_000;
const LARGE_CARDS = 3;
const OK = 200;

/** A view of another departure (a late one of the previous trip) is not for this view. */
function isFor(service: DriverService, view: DriverView): boolean {
  return (
    view.service === null ||
    (view.service.trip_id === service.trip_id && view.service.service_date === service.service_date)
  );
}

/** One state of the header: icon and short visible text, never colour alone (AC-08 v1.2). */
function headerState(ok: boolean, text: string) {
  return (
    <p
      className={`flex items-center gap-1.5 text-lg leading-tight font-bold ${ok ? 'text-occ-free-fg' : 'text-occ-full-fg'}`}
    >
      {ok ? <CheckIcon className="size-6 shrink-0" /> : <WarningIcon className="size-6 shrink-0" />}
      <span>{text}</span>
    </p>
  );
}

export interface DemandViewProps {
  service: DriverService;
  /** View already known when the page was loaded; null right after choosing the departure. */
  initialView: DriverView | null;
  /** Position, wake lock and views of the open shift, owned by ShiftPage (AC-04, AC-09). */
  shift: DriverShift;
  onNextDeparture: () => void;
  /** After confirming the end of the shift; a close by the server is handled by ShiftPage. */
  onSessionEnd: (reason: SessionCloseReason) => void;
}

/** Demand of the upcoming stops on the tablet (driver_ui.AC-04 … AC-10, docs/design.md §5.9). */
export function DemandView({
  service,
  initialView,
  shift,
  onNextDeparture,
  onSessionEnd,
}: DemandViewProps) {
  const { t } = useTranslation();
  const language = useUiLanguage();
  const heading = useRef<HTMLHeadingElement>(null);
  const [view, setView] = useState(initialView);
  const [muted, setMuted] = useState(() => safeStorage.get(MUTE_KEY) === 'true');
  const [highlighted, setHighlighted] = useState<ReadonlySet<string>>(new Set());
  const [confirming, setConfirming] = useState(false);
  const seen = useRef<ReadonlySet<string>>(
    initialView === null ? new Set() : diffAlerts(new Set(), initialView, true).seen,
  );
  const highlightTimers = useRef(new Map<string, ReturnType<typeof setTimeout>>());
  const ending = useRef(false);
  const endButton = useRef<HTMLButtonElement>(null);
  const received = useRef(initialView !== null);
  const lastGeneratedAt = useRef(
    initialView === null ? Number.NEGATIVE_INFINITY : Date.parse(initialView.generated_at),
  );
  const { permission, retryPermission, socketStatus, subscribeViews } = shift;

  function highlightStop(stopId: string) {
    const timers = highlightTimers.current;
    const existing = timers.get(stopId);
    if (existing !== undefined) clearTimeout(existing);
    setHighlighted((current) => new Set(current).add(stopId));
    timers.set(
      stopId,
      setTimeout(() => {
        timers.delete(stopId);
        setHighlighted((current) => {
          const next = new Set(current);
          next.delete(stopId);
          return next;
        });
      }, HIGHLIGHT_MS),
    );
  }

  // The first view this departure receives marks its requests as seen without a tone (AC-07),
  // as does the first one after reconnecting.
  function applyView(next: DriverView, initial: boolean) {
    const generatedAt = Date.parse(next.generated_at);
    if (!isFor(service, next) || generatedAt < lastGeneratedAt.current) return;
    lastGeneratedAt.current = generatedAt;
    const first = !received.current;
    received.current = true;
    const diff = diffAlerts(seen.current, next, initial || first);
    seen.current = diff.seen;
    setView(next);
    if (diff.fresh.length === 0) return;
    if (!muted) playTone();
    diff.fresh.forEach(({ stopId }) => highlightStop(stopId));
  }

  const onView = useRef<DriverViewListener>(() => undefined);
  useLayoutEffect(() => {
    onView.current = (next, meta) => applyView(next, meta.initial);
  });

  useEffect(() => subscribeViews((next, meta) => onView.current(next, meta)), [subscribeViews]);

  // Right after choosing the departure the socket is already open, so its next view may take a
  // while: the current one is asked for once.
  useEffect(() => {
    if (initialView !== null) return;
    let active = true;
    driverApi<DriverView>('GET', '/driver/sessions/current/view')
      .then((result) => {
        if (active && result.status === OK && result.data !== null) {
          onView.current(result.data, { initial: false });
        }
      })
      // A 401 is reported through loseDriverAuth; anything else waits for the socket.
      .catch(() => undefined);
    return () => {
      active = false;
    };
    // Only when the view is mounted.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const element = heading.current;
    if (element === null) return;
    element.tabIndex = -1;
    element.focus();
  }, []);

  useEffect(() => {
    const timers = highlightTimers.current;
    return () => {
      timers.forEach((timer) => clearTimeout(timer));
      timers.clear();
    };
  }, []);

  function toggleMute() {
    const next = !muted;
    setMuted(next);
    safeStorage.set(MUTE_KEY, String(next));
  }

  // "Seguir" or Escape: back to "Finalizar turno" (AC-10 v1.1). Explicitly, because WebKit does
  // not focus a button when it is clicked, so it has nothing to restore when the dialog closes.
  function cancelEnd() {
    setConfirming(false);
    endButton.current?.focus();
  }

  async function endShift() {
    if (ending.current) return;
    ending.current = true;
    // Whatever the answer, the shift ends here: the server closes it by itself if this one fails.
    await driverApi('DELETE', '/driver/sessions/current').catch(() => undefined);
    clearDriverToken();
    onSessionEnd('ENDED');
  }

  const stops = view?.stops ?? [];
  const nobodyWaiting = stops.length > 0 && stops.every((stop) => stop.waiting === 0);
  const large = stops.slice(0, LARGE_CARDS);
  const compact = stops.slice(LARGE_CARDS);
  const placesKnown = view !== null && view.free_places !== null && view.free_seats !== null;
  // Header state (AC-08 v1.2): two-valued, with the four texts of the spec. Anything but a fresh
  // fix with the permission granted is not a correct GPS; anything but an open socket is offline.
  const gpsOk = permission !== 'denied' && view?.gps === 'OK';
  const connected = socketStatus === 'connected';

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-1">
          <h1
            ref={heading}
            className="flex min-w-0 items-center gap-3 text-[1.375rem] leading-tight font-bold"
          >
            <LineBadge line={service.line} color={service.color} textColor={service.text_color} />
            <span>
              {t('stop.towards')} <GtfsText>{service.headsign}</GtfsText>
            </span>
          </h1>
          <p className="text-xl">
            {t('driver.demand.departure', {
              time: formatClockTime(service.departure_at, language),
            })}
          </p>
        </div>
        <div className="ml-auto flex flex-wrap items-center justify-end gap-x-5 gap-y-2">
          {headerState(gpsOk, t(gpsOk ? 'driver.status.gpsOk' : 'driver.status.gpsStale'))}
          {headerState(
            connected,
            t(connected ? 'driver.status.connected' : 'driver.status.offline'),
          )}
          <Button
            icon={<BellIcon muted={muted} className="size-[18px]" />}
            className="min-h-12"
            onClick={toggleMute}
          >
            {t(muted ? 'driver.unmute' : 'driver.mute')}
          </Button>
        </div>
      </div>

      <DriverStatus
        view={view}
        permission={permission}
        socketStatus={socketStatus}
        onRetryPermission={retryPermission}
        onNextDeparture={onNextDeparture}
      />
      {view !== null && <CapacityBanner view={view} />}
      {nobodyWaiting && (
        <p className="text-xl font-bold text-text-muted">{t('driver.demand.none')}</p>
      )}

      {large.length > 0 && (
        <ul className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {large.map((stop) => (
            <StopCard key={stop.stop_id} stop={stop} isNew={highlighted.has(stop.stop_id)} />
          ))}
        </ul>
      )}
      {compact.length > 0 && (
        <ul className="grid grid-cols-1 gap-3 md:grid-cols-2">
          {compact.map((stop) => (
            <StopCard
              key={stop.stop_id}
              stop={stop}
              compact
              isNew={highlighted.has(stop.stop_id)}
            />
          ))}
        </ul>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
        <p className="text-[1.375rem] font-bold">
          {view !== null &&
            (placesKnown
              ? t('driver.places', {
                  places: t('driver.freePlaces', { count: view.free_places }),
                  seats: t('driver.freeSeats', { count: view.free_seats }),
                })
              : t('driver.places.unknown'))}
        </p>
        <Button ref={endButton} className="min-h-12" onClick={() => setConfirming(true)}>
          {t('driver.end')}
        </Button>
      </div>

      {confirming && <EndShiftDialog onConfirm={() => void endShift()} onCancel={cancelEnd} />}
    </div>
  );
}
