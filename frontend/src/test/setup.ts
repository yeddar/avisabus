import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

import { resetPageTitleTracking } from '../shared/ui/usePageTitle';
import { FakeWebSocket } from './FakeWebSocket';

// No test may open a real WebSocket (no network in tests): every component gets the double.
globalThis.WebSocket = FakeWebSocket as unknown as typeof WebSocket;

/**
 * jsdom has <dialog> but not showModal()/close() (passenger_alert_ui design §5): a minimal
 * version with the parts the views use — `open`, the `close` event and Escape, which fires a
 * cancelable `cancel` and then closes. Focus trapping is checked in the e2e tests.
 */
if (
  typeof HTMLDialogElement !== 'undefined' &&
  typeof HTMLDialogElement.prototype.showModal !== 'function'
) {
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
    this.setAttribute('open', '');
  };
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement, value?: string) {
    if (!this.hasAttribute('open')) return;
    if (value !== undefined) this.returnValue = value;
    this.removeAttribute('open');
    this.dispatchEvent(new Event('close'));
  };
  document.addEventListener('keydown', (event) => {
    if (event.key !== 'Escape' || !(event.target instanceof Element)) return;
    const dialog = event.target.closest('dialog');
    if (dialog === null || !dialog.hasAttribute('open')) return;
    const cancel = new Event('cancel', { cancelable: true });
    if (dialog.dispatchEvent(cancel)) dialog.close();
  });
}

afterEach(() => {
  cleanup();
  resetPageTitleTracking();
  FakeWebSocket.reset();
});
