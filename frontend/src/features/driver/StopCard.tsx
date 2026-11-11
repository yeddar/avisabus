import { Trans, useTranslation } from 'react-i18next';

import { formatDistance } from '../../shared/i18n/format';
import { GtfsText } from '../../shared/i18n/GtfsText';
import { useUiLanguage } from '../passenger/stop/useUiLanguage';
import { NeedIcon } from './icons/NeedIcon';
import type { NeedCounts, StopDemand } from './types';

const NEEDS = [
  'RAMP',
  'EXTRA_TIME',
  'SEAT',
  'VISUAL',
] as const satisfies readonly (keyof NeedCounts)[];

export interface StopCardProps {
  stop: StopDemand;
  /** Stops 1–3 are large; 4 and 5 go in a compact row (docs/design.md §5.9). */
  compact?: boolean;
  /** A new request has just arrived for this stop (driver_ui.AC-07). */
  isNew?: boolean;
}

/** One upcoming stop with the people waiting and their needs (driver_ui.AC-05). */
export function StopCard({ stop, compact = false, isNew = false }: StopCardProps) {
  const { t } = useTranslation();
  const language = useUiLanguage();
  const needs = NEEDS.filter((need) => stop.needs[need] > 0);
  const figure = stop.waiting === 0 ? 'text-text-muted' : 'text-text';
  const border = isNew ? 'border-4 border-accent' : 'border border-border';

  return (
    <li
      className={`relative flex min-w-0 flex-col gap-2 rounded-[14px] p-3.5 ${border} ${compact ? '' : 'min-h-64'}`}
    >
      {isNew && (
        <span className="w-fit rounded-md bg-accent px-2 py-0.5 text-base font-bold text-white">
          {t('driver.demand.new')}
        </span>
      )}
      <p className={`font-bold ${compact ? 'text-lg' : 'line-clamp-2 text-2xl leading-tight'}`}>
        <GtfsText>{stop.name}</GtfsText>
      </p>
      <p className={`text-text-muted ${compact ? 'text-base' : 'text-lg'}`}>
        {formatDistance(stop.distance_m, language)}
      </p>
      <p className={`flex items-baseline gap-2 ${compact ? 'text-base' : 'text-lg'}`}>
        <Trans
          i18nKey="driver.demand.waiting"
          count={stop.waiting}
          components={{
            number: (
              <span
                className={`leading-none font-bold ${figure} ${compact ? 'text-[1.75rem]' : 'text-[4rem]'}`}
              />
            ),
          }}
        />
      </p>
      {needs.length > 0 && (
        <ul className={`flex flex-col gap-1 ${compact ? 'text-base' : 'text-xl'}`}>
          {needs.map((need) => (
            <li key={need} className="flex items-center gap-2">
              <NeedIcon need={need} className={`shrink-0 ${compact ? 'size-5' : 'size-7'}`} />
              {t(`driver.needs.${need}`, { count: stop.needs[need] })}
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}
