import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { ApiError } from '../../shared/api/client';
import { accessibleLineColors } from '../../shared/color/contrast';
import { formatClockTime } from '../../shared/i18n/format';
import { GtfsText } from '../../shared/i18n/GtfsText';
import { useAnnounce } from '../../shared/ui/Announcer';
import { ArrowLeftIcon } from '../../shared/ui/icons/ArrowLeftIcon';
import { RefreshIcon } from '../../shared/ui/icons/RefreshIcon';
import { Button } from '../../shared/ui/Button';
import { StatusNotice } from '../../shared/ui/StatusNotice';
import { useUiLanguage } from '../passenger/stop/useUiLanguage';
import { DriverAuthError, driverApi } from './session';
import type {
  Departure,
  DeparturesResponse,
  DriverLine,
  DriverService,
  LinesResponse,
} from './types';

const OK = 200;
const CONFLICT = 409;

type Step = 'line' | 'direction' | 'departure';

export interface ServicePickerProps {
  /** Starts directly at the departures of this line and direction (driver_ui.AC-08). */
  initialChoice?: { line: string; directionId: number };
  onSelected: (service: DriverService) => void;
  /** "Volver" on the first step: there is no earlier step inside the picker. */
  onExit: () => void;
}

function queryDriver<T>(path: string): () => Promise<T> {
  return async () => {
    const result = await driverApi<T>('GET', path);
    if (result.status !== OK || result.data === null) throw new ApiError(result.status, null);
    return result.data;
  };
}

/** /driver/shift without a departure: line → direction → departure (driver_ui.AC-02). */
export function ServicePicker({ initialChoice, onSelected, onExit }: ServicePickerProps) {
  const { t } = useTranslation();
  const language = useUiLanguage();
  const announce = useAnnounce();
  const queryClient = useQueryClient();
  const heading = useRef<HTMLHeadingElement>(null);
  const selecting = useRef(false);
  const [step, setStep] = useState<Step>(initialChoice === undefined ? 'line' : 'departure');
  const [line, setLine] = useState<string | null>(initialChoice?.line ?? null);
  const [directionId, setDirectionId] = useState<number | null>(initialChoice?.directionId ?? null);
  const [notice, setNotice] = useState<'taken' | 'failed' | null>(null);

  const lines = useQuery({
    queryKey: ['driver', 'lines'],
    queryFn: queryDriver<LinesResponse>('/driver/lines'),
    retry: false,
  });
  const departuresKey = ['driver', 'departures', line, directionId];
  const departures = useQuery({
    queryKey: departuresKey,
    queryFn: queryDriver<DeparturesResponse>(
      `/driver/departures?line=${encodeURIComponent(line ?? '')}&direction_id=${directionId ?? 0}`,
    ),
    enabled: step === 'departure' && line !== null && directionId !== null,
    retry: false,
  });

  const selectedLine: DriverLine | undefined = lines.data?.lines.find((l) => l.line === line);

  useEffect(() => {
    const element = heading.current;
    if (element === null) return;
    element.tabIndex = -1;
    element.focus();
  }, [step]);

  function goTo(next: Step) {
    setNotice(null);
    setStep(next);
  }

  async function choose(departure: Departure) {
    if (selecting.current || line === null || directionId === null) return;
    selecting.current = true;
    setNotice(null);
    try {
      const result = await driverApi('PUT', '/driver/sessions/current/service', {
        line,
        direction_id: directionId,
        trip_id: departure.trip_id,
        service_date: departure.service_date,
      });
      if (result.status === OK) {
        onSelected({
          line,
          direction_id: directionId,
          headsign: departure.headsign,
          trip_id: departure.trip_id,
          service_date: departure.service_date,
          departure_at: departure.departure_at,
          color: selectedLine?.color ?? '',
          text_color: selectedLine?.text_color ?? '',
        });
        return;
      }
      if (result.status === CONFLICT) {
        setNotice('taken');
        announce(t('driver.pick.takenNow'));
      } else {
        setNotice('failed');
      }
      void queryClient.invalidateQueries({ queryKey: departuresKey });
    } catch (failure) {
      if (!(failure instanceof DriverAuthError)) setNotice('failed');
    } finally {
      selecting.current = false;
    }
  }

  const failed =
    (step !== 'departure' && lines.isError && !(lines.error instanceof DriverAuthError)) ||
    (step === 'departure' && departures.isError && !(departures.error instanceof DriverAuthError));

  // Loads again what the current step shows; after a failed choice, the departures (AC-02 v1.2).
  function reload() {
    setNotice(null);
    void (step === 'departure' ? departures.refetch() : lines.refetch());
  }

  return (
    <div className="mx-auto flex w-full max-w-[560px] flex-col gap-5">
      <h1 ref={heading} className="text-[1.75rem] leading-[1.15] font-bold">
        {step === 'line' && t('driver.pick.line')}
        {step === 'direction' && t('driver.pick.direction')}
        {step === 'departure' && t('driver.pick.departure')}
      </h1>

      {notice === 'taken' && <StatusNotice>{t('driver.pick.takenNow')}</StatusNotice>}
      {(notice === 'failed' || failed) && (
        <StatusNotice
          action={
            <Button icon={<RefreshIcon className="size-[18px]" />} onClick={reload}>
              {t('driver.pick.retry')}
            </Button>
          }
        >
          <strong>{t('driver.pick.error')}</strong>
        </StatusNotice>
      )}

      {step === 'line' && lines.data !== undefined && (
        <ul className="flex flex-wrap gap-3">
          {lines.data.lines.map((item) => {
            const colors = accessibleLineColors(item.color, item.text_color);
            return (
              <li key={item.line}>
                <button
                  type="button"
                  aria-label={t('driver.pick.lineLabel', { line: item.line })}
                  onClick={() => {
                    setLine(item.line);
                    goTo('direction');
                  }}
                  className="inline-flex min-h-16 min-w-16 items-center justify-center rounded-[10px] px-2 text-[1.375rem] leading-none font-bold"
                  style={{ backgroundColor: colors.bg, color: colors.fg }}
                >
                  {item.line}
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {step === 'direction' && selectedLine !== undefined && (
        <ul className="flex flex-col gap-3">
          {selectedLine.directions.map((direction) => (
            <li key={direction.direction_id}>
              <Button
                className="min-h-16 w-full text-xl"
                onClick={() => {
                  setDirectionId(direction.direction_id);
                  goTo('departure');
                }}
              >
                <GtfsText>{direction.headsign}</GtfsText>
              </Button>
            </li>
          ))}
        </ul>
      )}

      {step === 'departure' && departures.data !== undefined && (
        <>
          {departures.data.departures.length === 0 && (
            <StatusNotice
              action={
                <Button icon={<RefreshIcon className="size-[18px]" />} onClick={reload}>
                  {t('driver.pick.refresh')}
                </Button>
              }
            >
              <strong>{t('driver.pick.empty')}</strong>
            </StatusNotice>
          )}
          <ul className="flex flex-col gap-3">
            {departures.data.departures.map((departure) => (
              <li key={`${departure.trip_id}-${departure.service_date}`}>
                <button
                  type="button"
                  disabled={departure.taken}
                  onClick={() => void choose(departure)}
                  className="flex min-h-16 w-full items-center gap-4 rounded-[10px] border-2 border-accent bg-surface px-4 py-2 text-left text-text disabled:cursor-not-allowed disabled:border-control-border disabled:text-text-muted"
                >
                  <span className="shrink-0 text-[1.75rem] leading-none font-bold">
                    {formatClockTime(departure.departure_at, language)}
                  </span>
                  <span className="flex min-w-0 flex-col">
                    <GtfsText>{departure.first_stop_name}</GtfsText>
                    <span>
                      {t('stop.towards')} <GtfsText>{departure.headsign}</GtfsText>
                    </span>
                  </span>
                  {departure.taken && (
                    <span className="ml-auto shrink-0 font-bold">{t('driver.pick.taken')}</span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}

      <div>
        <Button
          icon={<ArrowLeftIcon className="size-[18px]" />}
          className="min-h-12"
          onClick={() => {
            if (step === 'line') onExit();
            else goTo(step === 'departure' ? 'direction' : 'line');
          }}
        >
          {t('driver.pick.back')}
        </Button>
      </div>
    </div>
  );
}
