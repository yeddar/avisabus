import { Trans } from 'react-i18next';

import type { ArrivalSource } from '../../../shared/api/types';
import { StatusNotice } from '../../../shared/ui/StatusNotice';

/** Notice shown above the list when the times come from the timetable (passenger_stop_view.AC-09). */
export function SourceNotice({ source }: { source: ArrivalSource }) {
  if (source !== 'SCHEDULED') return null;
  return (
    <StatusNotice role="status">
      <Trans i18nKey="stop.scheduledNotice" components={{ strong: <strong /> }} />
    </StatusNotice>
  );
}
