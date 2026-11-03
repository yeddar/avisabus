import { QueryClient, onlineManager } from '@tanstack/react-query';

/**
 * TanStack Query assumes it is online until an `offline` event arrives; this also takes the
 * initial state from the browser, so a page opened without connection does not call the API
 * until it is back (passenger_stop_view.AC-18).
 */
function followBrowserConnection(): void {
  onlineManager.setEventListener((setOnline) => {
    const update = () => setOnline(navigator.onLine);
    update();
    window.addEventListener('online', update);
    window.addEventListener('offline', update);
    return () => {
      window.removeEventListener('online', update);
      window.removeEventListener('offline', update);
    };
  });
}

/**
 * QueryClient of the application. Each query sets its own refresh and retry policy (see
 * features/passenger/stop/useStopQueries.ts); these are only the shared defaults.
 */
export function createQueryClient(): QueryClient {
  followBrowserConnection();
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
