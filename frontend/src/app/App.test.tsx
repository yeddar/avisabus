import { render, screen } from '@testing-library/react';
import { RouterProvider, createMemoryRouter } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { routes } from './routes';

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  return render(<RouterProvider router={router} />);
}

describe('App routes', () => {
  it('[project_scaffold.AC-16] renders the home page with a single h1 inside a main landmark', () => {
    renderAt('/');

    const main = screen.getByRole('main');
    const headings = screen.getAllByRole('heading', { level: 1 });
    expect(headings).toHaveLength(1);
    expect(main).toContainElement(headings[0] ?? null);
    expect(screen.getAllByRole('main')).toHaveLength(1);
  });
});
