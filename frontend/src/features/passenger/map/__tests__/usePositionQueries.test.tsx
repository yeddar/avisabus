import { QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { createQueryClient } from '../../../../shared/api/queryClient';
import { POSITION_EN_ROUTE, SHAPE_93 } from '../../../../test/fixtures/api';
import {
  deferred,
  mockApi,
  ok,
  problem,
  setVisibility,
  type FakeReply,
} from '../../../../test/mockApi';
import { usePosition, useShape } from '../usePositionQueries';

const TOKEN = 'AbCdEfGhIjKlMnOpQrStUv';
const SHAPE_NOT_FOUND = 'https://avisabus/problems/shape-not-found';

function wrapper() {
  const client = createQueryClient();
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

async function flush(ms = 0) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

describe('usePosition and useShape', () => {
  let positionReply: () => FakeReply | Promise<FakeReply>;
  let shapeReply: () => FakeReply;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(Date.parse('2026-11-04T07:40:00Z'));
    positionReply = () => ok(POSITION_EN_ROUTE());
    shapeReply = () => ok(SHAPE_93());
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    setVisibility('visible');
  });

  function api() {
    return mockApi((url) => {
      if (url.pathname === '/api/v1/stops/508/lines/93/position') return positionReply();
      if (url.pathname.startsWith('/api/v1/shapes/')) return shapeReply();
      throw new Error(`unexpected request ${url.pathname}`);
    });
  }

  it('[passenger_map_view.AC-12] asks for the position of the line and direction with the token', async () => {
    const { fetchMock } = api();
    const { result } = renderHook(() => usePosition('508', TOKEN, '93', 0), { wrapper: wrapper() });
    await flush();

    expect(String(fetchMock.mock.calls[0]?.[0])).toBe(
      `/api/v1/stops/508/lines/93/position?direction_id=0&t=${TOKEN}`,
    );
    expect(result.current.data?.status).toBe('EN_ROUTE');
  });

  it('[passenger_map_view.AC-12] refreshes every min(refresh_after_s, 30) s', async () => {
    const { calls } = api();
    renderHook(() => usePosition('508', TOKEN, '93', 0), { wrapper: wrapper() });
    await flush();
    expect(calls('/position')).toBe(1);
    await flush(19_999);
    expect(calls('/position')).toBe(1);
    await flush(1);
    expect(calls('/position')).toBe(2);

    positionReply = () => ok({ ...POSITION_EN_ROUTE(), refresh_after_s: 60 });
    await flush(20_000);
    expect(calls('/position')).toBe(3);
    await flush(29_999);
    expect(calls('/position')).toBe(3);
    await flush(1);
    expect(calls('/position')).toBe(4);
  });

  it('[passenger_map_view.AC-12] pauses while the tab is hidden and refreshes at once when visible again', async () => {
    const { calls } = api();
    renderHook(() => usePosition('508', TOKEN, '93', 0), { wrapper: wrapper() });
    await flush();

    act(() => setVisibility('hidden'));
    await flush(120_000);
    expect(calls('/position')).toBe(1);

    act(() => setVisibility('visible'));
    await flush();
    expect(calls('/position')).toBe(2);
  });

  it('[passenger_map_view.AC-12] keeps the previous position while a refresh is in flight', async () => {
    const { calls } = api();
    const { result } = renderHook(() => usePosition('508', TOKEN, '93', 0), {
      wrapper: wrapper(),
    });
    await flush();
    const pending = deferred<FakeReply>();
    positionReply = () => pending.promise;
    await flush(20_000);
    expect(calls('/position')).toBe(2); // and its answer is still pending

    expect(result.current.data?.status).toBe('EN_ROUTE');
  });

  it('[passenger_map_view.AC-12] asks for a shape once and reuses it', async () => {
    const { calls, fetchMock } = api();
    const run = wrapper();
    const first = renderHook(() => useShape('994_488_2271'), { wrapper: run });
    await flush();
    const second = renderHook(() => useShape('994_488_2271'), { wrapper: run });
    await flush(120_000);

    expect(calls('/shapes/')).toBe(1);
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe('/api/v1/shapes/994_488_2271');
    expect(first.result.current.data?.shape_id).toBe('994_488_2271');
    expect(second.result.current.data?.shape_id).toBe('994_488_2271');
  });

  it('[passenger_map_view.AC-12] does not ask for a shape without shape_id', async () => {
    const { fetchMock } = api();
    const { result } = renderHook(() => useShape(null), { wrapper: wrapper() });
    await flush(60_000);

    expect(fetchMock).not.toHaveBeenCalled();
    expect(result.current.fetchStatus).toBe('idle');
  });

  it('[passenger_map_view.AC-12] does not retry a shape that does not exist', async () => {
    shapeReply = () => problem(404, SHAPE_NOT_FOUND);
    const { calls } = api();
    const { result } = renderHook(() => useShape('x'), { wrapper: wrapper() });
    await flush(10_000);

    expect(calls('/shapes/')).toBe(1);
    expect(result.current.error?.status).toBe(404);
  });
});
