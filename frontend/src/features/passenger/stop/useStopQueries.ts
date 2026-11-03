import { keepPreviousData, useQuery, type UseQueryResult } from '@tanstack/react-query';

import { type ApiError, apiGet } from '../../../shared/api/client';
import type { StopArrivalsResponse, StopResponse } from '../../../shared/api/types';

/** Default refresh when the API has not said yet, and the maximum (RF-10). */
const DEFAULT_REFRESH_S = 20;
const MAX_REFRESH_S = 30;

const retry = (failures: number, error: ApiError) => error.status !== 404 && failures < 2;

function stopPath(stopId: string, token: string, suffix = ''): string {
  return `/stops/${encodeURIComponent(stopId)}${suffix}?t=${encodeURIComponent(token)}`;
}

/** Stop name and lines. They do not change while the page is open. */
export function useStop(stopId: string, token: string): UseQueryResult<StopResponse, ApiError> {
  return useQuery<StopResponse, ApiError>({
    queryKey: ['stop', stopId, token],
    queryFn: ({ signal }) => apiGet<StopResponse>(stopPath(stopId, token), { signal }),
    staleTime: Infinity,
    retry,
    networkMode: 'online',
  });
}

/**
 * Next arrivals, refreshed every min(refresh_after_s, 30) s only while the page is visible, and
 * at once when it becomes visible again (passenger_stop_view.AC-12, design §3).
 */
export function useStopArrivals(
  stopId: string,
  token: string,
): UseQueryResult<StopArrivalsResponse, ApiError> {
  return useQuery<StopArrivalsResponse, ApiError>({
    queryKey: ['arrivals', stopId, token],
    queryFn: ({ signal }) =>
      apiGet<StopArrivalsResponse>(stopPath(stopId, token, '/arrivals'), { signal }),
    refetchInterval: (query) =>
      Math.min(query.state.data?.refresh_after_s ?? DEFAULT_REFRESH_S, MAX_REFRESH_S) * 1000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    placeholderData: keepPreviousData,
    retry,
    networkMode: 'online',
  });
}
