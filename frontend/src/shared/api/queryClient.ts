import { QueryClient } from '@tanstack/react-query';

/**
 * QueryClient of the application. Each query sets its own refresh and retry policy (see
 * features/passenger/stop/useStopQueries.ts); these are only the shared defaults.
 */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        networkMode: 'online',
        refetchOnWindowFocus: true,
        staleTime: 0,
      },
    },
  });
}
