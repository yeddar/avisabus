import type { RouteObject } from 'react-router-dom';

import { Layout } from './Layout';
import { HomePage } from './routes/HomePage';

export const routes: RouteObject[] = [
  {
    element: <Layout />,
    children: [{ path: '/', element: <HomePage /> }],
  },
];
