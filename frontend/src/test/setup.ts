import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

import { resetPageTitleTracking } from '../shared/ui/usePageTitle';
import { FakeWebSocket } from './FakeWebSocket';

// No test may open a real WebSocket (no network in tests): every component gets the double.
globalThis.WebSocket = FakeWebSocket as unknown as typeof WebSocket;

afterEach(() => {
  cleanup();
  resetPageTitleTracking();
  FakeWebSocket.reset();
});
