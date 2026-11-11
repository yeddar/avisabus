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

/** The driver view is not part of the passenger's initial JavaScript (driver_ui design §1). */
const DriverLayout = lazy(() =>
  import('../features/driver/DriverLayout').then((module) => ({ default: module.DriverLayout })),
);
const LoginPage = lazy(() =>
  import('../features/driver/LoginPage').then((module) => ({ default: module.LoginPage })),
);
const ShiftPage = lazy(() =>
  import('../features/driver/ShiftPage').then((module) => ({ default: module.ShiftPage })),
);

export const routes: RouteObject[] = [
  {
    element: (
      <Suspense fallback={null}>
        <DriverLayout />
      </Suspense>
    ),
    children: [
      { path: '/driver', element: <LoginPage /> },
      { path: '/driver/shift', element: <ShiftPage /> },
    ],
  },
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
