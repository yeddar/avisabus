import { keepPreviousData, useQuery, type UseQueryResult } from '@tanstack/react-query';

import { type ApiError, apiGet } from '../../../shared/api/client';
import type { PositionResponse, ShapeResponse } from '../../../shared/api/types';
import { isNotFound } from '../stop/useStopQueries';

/** Same refresh as the stop view (RF-10): 20 s until the API says, never more than 30 s. */
const DEFAULT_REFRESH_S = 20;
const MAX_REFRESH_S = 30;

/** A 404 is final; other errors are retried twice (1 s and 2 s later), as in the stop view. */
const retry = (failures: number, error: ApiError) => !isNotFound(error) && failures < 2;

/**
 * Estimated position of the first bus of a line and direction at the stop, refreshed every
 * min(refresh_after_s, 30) s only while the page is visible, and at once when it becomes visible
 * again (passenger_map_view.AC-12, same options as useStopArrivals).
 */
export function usePosition(
  stopId: string,
  token: string,
  line: string,
  directionId: number,
): UseQueryResult<PositionResponse, ApiError> {
  const path =
    `/stops/${encodeURIComponent(stopId)}/lines/${encodeURIComponent(line)}/position` +
    `?direction_id=${directionId}&t=${encodeURIComponent(token)}`;
  return useQuery<PositionResponse, ApiError>({
    queryKey: ['position', stopId, token, line, directionId],
    queryFn: ({ signal }) => apiGet<PositionResponse>(path, { signal }),
    refetchInterval: (query) =>
      isNotFound(query.state.error)
        ? false
        : Math.min(query.state.data?.refresh_after_s ?? DEFAULT_REFRESH_S, MAX_REFRESH_S) * 1000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    placeholderData: keepPreviousData,
    retry,
    networkMode: 'online',
  });
}

/**
 * Shape of a trip: asked once per shape_id and reused (passenger_map_view.AC-12); not asked
 * without a shape_id.
 */
export function useShape(shapeId: string | null): UseQueryResult<ShapeResponse, ApiError> {
  return useQuery<ShapeResponse, ApiError>({
    queryKey: ['shape', shapeId],
    queryFn: ({ signal }) =>
      apiGet<ShapeResponse>(`/shapes/${encodeURIComponent(shapeId ?? '')}`, { signal }),
    enabled: shapeId !== null,
    staleTime: Infinity,
    refetchOnWindowFocus: false,
    retry,
    networkMode: 'online',
  });
}
