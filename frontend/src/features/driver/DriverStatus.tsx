import { useTranslation } from 'react-i18next';

import { Button } from '../../shared/ui/Button';
import { StatusNotice } from '../../shared/ui/StatusNotice';
import type { DriverView } from './types';
import type { LocationPermission } from './useDriverPosition';
import type { DriverSocketStatus } from './useDriverSocket';

export interface DriverStatusProps {
  view: DriverView | null;
  permission: LocationPermission;
  socketStatus: DriverSocketStatus;
  onRetryPermission: () => void;
  onNextDeparture: () => void;
}

/** First sentence in bold up to the first punctuation mark (docs/design.md §5.6). */
function emphasize(text: string) {
  const end = text.search(/[:.…]/);
  if (end === -1) return <strong>{text}</strong>;
  return (
    <>
      <strong>{text.slice(0, end + 1)}</strong>
      {text.slice(end + 1)}
    </>
  );
}

/** GPS, route, connection and end-of-route states (driver_ui.AC-04, AC-08; design §5.9). */
export function DriverStatus({
  view,
  permission,
  socketStatus,
  onRetryPermission,
  onNextDeparture,
}: DriverStatusProps) {
  const { t } = useTranslation();
  const denied = permission === 'denied';
  const gps = view?.gps;

  return (
    <>
      {denied && (
        <StatusNotice
          role="status"
          action={<Button onClick={onRetryPermission}>{t('driver.gps.retry')}</Button>}
        >
          {emphasize(t('driver.gps.denied'))}
        </StatusNotice>
      )}
      {!denied && gps === 'WAITING' && (
        <StatusNotice role="status">{emphasize(t('driver.gps.waiting'))}</StatusNotice>
      )}
      {!denied && gps === 'STALE' && (
        <StatusNotice role="status">{emphasize(t('driver.gps.stale'))}</StatusNotice>
      )}
      {view?.off_route === true && (
        <StatusNotice role="status">{emphasize(t('driver.offRoute'))}</StatusNotice>
      )}
      {socketStatus === 'disconnected' && (
        <StatusNotice role="status">{emphasize(t('driver.offline'))}</StatusNotice>
      )}
      {view?.finished === true && (
        <StatusNotice
          role="status"
          action={
            <Button variant="primary" onClick={onNextDeparture}>
              {t('driver.nextDeparture')}
            </Button>
          }
        >
          {emphasize(t('driver.finished'))}
        </StatusNotice>
      )}
    </>
  );
}
