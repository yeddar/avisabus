import { useTranslation } from 'react-i18next';

import type { Occupancy, OccupancyLevel } from '../../../shared/api/types';
import { OccupancyIcon } from './OccupancyIcon';

/** Background / text and icon colours of docs/design.md §4 (all ≥ 6.8:1). */
const STYLES: Record<OccupancyLevel | 'none', string> = {
  FREE: 'bg-occ-free-bg text-occ-free-fg',
  MEDIUM: 'bg-occ-medium-bg text-occ-medium-fg',
  FULL: 'bg-occ-full-bg text-occ-full-fg',
  none: 'bg-occ-none-bg text-occ-none-fg',
};

const FILLED: Record<OccupancyLevel, number> = { FREE: 1, MEDIUM: 2, FULL: 3 };

/**
 * Occupancy badge of docs/design.md §5.4: icon and "**Level** · seats", never colour alone
 * (passenger_stop_view.AC-07).
 */
export function OccupancyInfo({ occupancy }: { occupancy: Occupancy | null }) {
  const { t } = useTranslation();
  const style = STYLES[occupancy?.level ?? 'none'];

  return (
    <div
      className={`flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[0.9375rem] leading-snug ${style}`}
    >
      <OccupancyIcon filled={occupancy === null ? 0 : FILLED[occupancy.level]} />
      {occupancy === null ? (
        <strong>{t('occupancy.unavailable')}</strong>
      ) : (
        <span>
          <strong>{t(`occupancy.${occupancy.level}`)}</strong>
          <span className="before:mx-1.5 before:content-['·']">
            {t(occupancy.has_free_seats ? 'occupancy.seatsYes' : 'occupancy.seatsNo')}
          </span>
        </span>
      )}
    </div>
  );
}
