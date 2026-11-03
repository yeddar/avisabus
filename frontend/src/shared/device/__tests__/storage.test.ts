import { afterEach, describe, expect, it, vi } from 'vitest';

import { safeStorage } from '../storage';

describe('safeStorage', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it('reads and writes localStorage', () => {
    safeStorage.set('avisabus.test', 'value');

    expect(safeStorage.get('avisabus.test')).toBe('value');
    expect(localStorage.getItem('avisabus.test')).toBe('value');
  });

  it('returns null for a missing key', () => {
    expect(safeStorage.get('avisabus.missing')).toBeNull();
  });

  it('swallows storage errors (private mode, quota, disabled storage)', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('SecurityError');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceededError');
    });

    expect(() => safeStorage.set('avisabus.test', 'value')).not.toThrow();
    expect(safeStorage.get('avisabus.test')).toBeNull();
  });
});
