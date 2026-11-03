import { afterEach, describe, expect, it, vi } from 'vitest';

import { LAST_STOP_STORAGE_KEY, getLastStop, setLastStop } from '../lastStop';

const STOP = { stopId: '508', name: "Parc de l'Oest - Enguera", token: 'AAAAAAAAAAAAAAAAAAAAAA' };

describe('lastStop', () => {
  afterEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it('[passenger_stop_view.AC-19] remembers the stop id, name and token on the device', () => {
    setLastStop(STOP);

    expect(LAST_STOP_STORAGE_KEY).toBe('avisabus.lastStop');
    expect(JSON.parse(localStorage.getItem('avisabus.lastStop') ?? 'null')).toEqual(STOP);
    expect(getLastStop()).toEqual(STOP);
  });

  it('[passenger_stop_view.AC-19] keeps only the latest stop', () => {
    setLastStop(STOP);
    setLastStop({ stopId: '2070', name: 'Plaça Espanya', token: 'BBBBBBBBBBBBBBBBBBBBBB' });

    expect(getLastStop()?.stopId).toBe('2070');
  });

  it('[passenger_stop_view.AC-19] returns null when nothing valid is stored', () => {
    expect(getLastStop()).toBeNull();

    localStorage.setItem('avisabus.lastStop', '{not json');
    expect(getLastStop()).toBeNull();

    localStorage.setItem('avisabus.lastStop', JSON.stringify({ stopId: '508' }));
    expect(getLastStop()).toBeNull();

    localStorage.setItem('avisabus.lastStop', JSON.stringify({ ...STOP, name: 7 }));
    expect(getLastStop()).toBeNull();
  });

  it('[passenger_stop_view.AC-19] degrades to nothing remembered when storage is unavailable', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('QuotaExceededError');
    });
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('SecurityError');
    });

    expect(() => setLastStop(STOP)).not.toThrow();
    expect(getLastStop()).toBeNull();
  });
});
