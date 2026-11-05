import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  NEEDS,
  NEEDS_PROFILE_STORAGE_KEY,
  clearNeedsProfile,
  getNeedsProfile,
  setNeedsProfile,
} from '../needsProfile';

describe('needs profile', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it('[passenger_alert_ui.AC-02] lists the four needs in canonical order', () => {
    expect(NEEDS).toEqual(['RAMP', 'EXTRA_TIME', 'SEAT', 'VISUAL']);
  });

  it('[passenger_alert_ui.AC-02] is empty when nothing is stored', () => {
    expect(getNeedsProfile()).toEqual([]);
  });

  it('[passenger_alert_ui.AC-02] stores the profile only on the device, as JSON in canonical order', () => {
    setNeedsProfile(['VISUAL', 'RAMP']);

    expect(NEEDS_PROFILE_STORAGE_KEY).toBe('avisabus.needsProfile');
    expect(localStorage.getItem('avisabus.needsProfile')).toBe('["RAMP","VISUAL"]');
    expect(getNeedsProfile()).toEqual(['RAMP', 'VISUAL']);
  });

  it('[passenger_alert_ui.AC-02] clears the profile from the device', () => {
    setNeedsProfile(['SEAT']);

    clearNeedsProfile();

    expect(localStorage.getItem('avisabus.needsProfile')).toBeNull();
    expect(getNeedsProfile()).toEqual([]);
  });

  it.each([
    ['not json', '{oops'],
    ['not a list', '{"RAMP":true}'],
    ['unknown values only', '["WINGS", 3]'],
  ])(
    '[passenger_alert_ui.AC-02] reads an invalid stored value (%s) as an empty profile',
    (_, raw) => {
      localStorage.setItem('avisabus.needsProfile', raw);

      expect(getNeedsProfile()).toEqual([]);
    },
  );

  it('[passenger_alert_ui.AC-02] keeps only known needs, once, in canonical order', () => {
    localStorage.setItem('avisabus.needsProfile', '["SEAT","WINGS","RAMP","SEAT"]');

    expect(getNeedsProfile()).toEqual(['RAMP', 'SEAT']);
  });

  it('[passenger_alert_ui.AC-02] does not fail without storage', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError');
    });
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
      throw new Error('SecurityError');
    });

    expect(() => setNeedsProfile(['RAMP'])).not.toThrow();
    expect(() => clearNeedsProfile()).not.toThrow();
  });
});
