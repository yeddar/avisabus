import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

const UUID_V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const STORED = '0f8e2c1a-5b7d-4e3f-9a6c-1d2e3f4a5b6c';

/** Fresh module per test: the in-memory identifier must not leak between tests. */
async function loadDeviceId() {
  vi.resetModules();
  return import('../deviceId');
}

describe('getDeviceId', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  it('[passenger_alert_ui.AC-01] creates a random UUID v4 with crypto.randomUUID the first time and stores it', async () => {
    const randomUUID = vi.spyOn(crypto, 'randomUUID');
    const { getDeviceId, DEVICE_ID_STORAGE_KEY } = await loadDeviceId();

    const id = getDeviceId();

    expect(DEVICE_ID_STORAGE_KEY).toBe('avisabus.deviceId');
    expect(randomUUID).toHaveBeenCalledTimes(1);
    expect(id).toMatch(UUID_V4);
    expect(localStorage.getItem('avisabus.deviceId')).toBe(id);
    expect(getDeviceId()).toBe(id);
    expect(randomUUID).toHaveBeenCalledTimes(1);
  });

  it('[passenger_alert_ui.AC-01] reuses the identifier stored on the device', async () => {
    localStorage.setItem('avisabus.deviceId', STORED);
    const randomUUID = vi.spyOn(crypto, 'randomUUID');
    const { getDeviceId } = await loadDeviceId();

    expect(getDeviceId()).toBe(STORED);
    expect(randomUUID).not.toHaveBeenCalled();
  });

  it('[passenger_alert_ui.AC-01] replaces a stored value that is not a UUID v4', async () => {
    localStorage.setItem('avisabus.deviceId', 'not-a-uuid');
    const { getDeviceId } = await loadDeviceId();

    const id = getDeviceId();

    expect(id).toMatch(UUID_V4);
    expect(localStorage.getItem('avisabus.deviceId')).toBe(id);
  });

  it('[passenger_alert_ui.AC-01] without storage keeps one identifier in memory for the session', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('SecurityError');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('SecurityError');
    });
    const { getDeviceId } = await loadDeviceId();

    const id = getDeviceId();

    expect(id).toMatch(UUID_V4);
    expect(getDeviceId()).toBe(id);
    expect(getDeviceId()).toBe(id);
  });
});
