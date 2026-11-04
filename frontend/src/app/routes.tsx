import { lazy, Suspense } from 'react';
import type { RouteObject } from 'react-router-dom';

import { NeedsPage } from '../features/passenger/alerts/NeedsPage';
import { MapLoading } from '../features/passenger/map/MapLoading';
import { StopPage } from '../features/passenger/stop/StopPage';
import { Layout } from './Layout';
import { HomePage } from './routes/HomePage';
import { NotFoundPage } from './routes/NotFoundPage';

/** The map and Leaflet load in their own chunk (passenger_map_view.AC-02). */
const MapPage = lazy(() =>
  import('../features/passenger/map/MapPage').then((module) => ({ default: module.MapPage })),
);

export const routes: RouteObject[] = [
  {
    element: <Layout />,
    children: [
      { path: '/', element: <HomePage /> },
      { path: '/p/:stopId', element: <StopPage /> },
      { path: '/necesidades', element: <NeedsPage /> },
      {
        path: '/p/:stopId/map/:line/:directionId',
        element: (
          <Suspense fallback={<MapLoading />}>
            <MapPage />
          </Suspense>
        ),
      },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
];
