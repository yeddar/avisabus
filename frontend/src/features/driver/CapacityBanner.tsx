import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';

import { useAnnounce } from '../../shared/ui/Announcer';
import { WarningIcon } from './icons/WarningIcon';
import type { DriverView } from './types';

const STRIP =
  'flex items-center gap-3 rounded-xl border-[3px] border-occ-full-fg bg-occ-full-bg p-3 ' +
  'text-[1.625rem] leading-tight font-bold text-occ-full-fg';

/**
 * Capacity and seat strips (driver_ui.AC-06, docs/design.md §5.9). A strip is announced once when
 * it appears, through the assertive region of the Announcer (role="alert", frontend_i18n.AC-12):
 * the region is not the strip, so its numbers can change without announcing it again, and strips
 * that appear together are announced in one message.
 */
export function CapacityBanner({ view }: { view: DriverView }) {
  const { t } = useTranslation();
  const announce = useAnnounce();
  const announced = useRef({ capacity: false, seat: false });

  const capacityText = view.capacity_alert
    ? t('driver.capacity', { waiting: view.total_waiting, places: view.free_places })
    : null;
  const seatRequests = view.stops.reduce((total, stop) => total + stop.needs.SEAT, 0);
  const seatText = view.seat_alert
    ? t('driver.seats', { requests: seatRequests, seats: view.free_seats })
    : null;

  useEffect(() => {
    const appeared: string[] = [];
    if (capacityText !== null && !announced.current.capacity) appeared.push(capacityText);
    if (seatText !== null && !announced.current.seat) appeared.push(seatText);
    announced.current = { capacity: capacityText !== null, seat: seatText !== null };
    if (appeared.length > 0) announce(appeared.join('. '), 'assertive');
  }, [announce, capacityText, seatText]);

  if (capacityText === null && seatText === null) return null;

  return (
    <div className="flex flex-col gap-3">
      {capacityText !== null && (
        <p className={STRIP}>
          <WarningIcon className="size-8 shrink-0" />
          {capacityText}
        </p>
      )}
      {seatText !== null && (
        <p className={STRIP}>
          <WarningIcon className="size-8 shrink-0" />
          {seatText}
        </p>
      )}
    </div>
  );
}
