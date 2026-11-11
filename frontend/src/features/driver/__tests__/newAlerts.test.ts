import { describe, expect, it } from 'vitest';

import { diffAlerts } from '../newAlerts';
import { driverView, stopDemand } from './fixtures';

const view = driverView({
  stops: [
    stopDemand({ stop_id: '508', alert_ids: ['a', 'b'] }),
    stopDemand({ stop_id: '509', alert_ids: ['c'] }),
  ],
});

describe('diffAlerts', () => {
  it('[driver_ui.AC-07] the first view marks its requests as seen without any fresh one', () => {
    const { seen, fresh } = diffAlerts(new Set(), view, true);

    expect([...seen].sort()).toEqual(['a', 'b', 'c']);
    expect(fresh).toEqual([]);
  });

  it('[driver_ui.AC-07] reports the alert ids not seen before, with their stop', () => {
    const { seen, fresh } = diffAlerts(new Set(['a']), view, false);

    expect(fresh).toEqual([
      { alertId: 'b', stopId: '508' },
      { alertId: 'c', stopId: '509' },
    ]);
    expect([...seen].sort()).toEqual(['a', 'b', 'c']);
  });

  it('[driver_ui.AC-07] keeps remembering requests that left the view', () => {
    const { seen, fresh } = diffAlerts(
      new Set(['old']),
      driverView({ stops: [stopDemand({ alert_ids: ['old'] })] }),
      false,
    );

    expect([...seen]).toEqual(['old']);
    expect(fresh).toEqual([]);
  });
});
