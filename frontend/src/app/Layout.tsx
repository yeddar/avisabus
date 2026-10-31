import { Outlet } from 'react-router-dom';

export function Layout() {
  return (
    <div className="min-h-dvh bg-white text-gray-900">
      <Outlet />
    </div>
  );
}
