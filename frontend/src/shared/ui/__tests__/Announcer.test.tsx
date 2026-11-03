import { act, render, renderHook, screen } from '@testing-library/react';
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AnnouncerProvider, useAnnounce } from '../Announcer';

function Speaker({
  message,
  politeness,
}: {
  message: string;
  politeness?: 'polite' | 'assertive';
}) {
  const announce = useAnnounce();
  return (
    <button type="button" onClick={() => announce(message, politeness)}>
      speak
    </button>
  );
}

function nextFrame() {
  act(() => {
    vi.advanceTimersToNextFrame();
  });
}

describe('Announcer', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['requestAnimationFrame', 'cancelAnimationFrame'] });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('[frontend_i18n.AC-12] provides one polite and one assertive visually hidden live region', () => {
    render(
      <AnnouncerProvider>
        <p>content</p>
      </AnnouncerProvider>,
    );

    const status = screen.getByRole('status');
    const alert = screen.getByRole('alert');
    expect(status).toHaveAttribute('aria-live', 'polite');
    expect(alert).toHaveAttribute('aria-live', 'assertive');
    expect(status).toHaveClass('sr-only');
    expect(alert).toHaveClass('sr-only');
  });

  it('[frontend_i18n.AC-12] announces politely by default through the hook', () => {
    render(
      <AnnouncerProvider>
        <Speaker message="Bus 93 in 4 minutes" />
      </AnnouncerProvider>,
    );

    act(() => screen.getByRole('button').click());
    nextFrame();

    expect(screen.getByRole('status')).toHaveTextContent('Bus 93 in 4 minutes');
    expect(screen.getByRole('alert')).toBeEmptyDOMElement();
  });

  it('[frontend_i18n.AC-12] announces assertively when asked', () => {
    render(
      <AnnouncerProvider>
        <Speaker message="Bus full" politeness="assertive" />
      </AnnouncerProvider>,
    );

    act(() => screen.getByRole('button').click());
    nextFrame();

    expect(screen.getByRole('alert')).toHaveTextContent('Bus full');
    expect(screen.getByRole('status')).toBeEmptyDOMElement();
  });

  it('[frontend_i18n.AC-12] repeats the same message by clearing the region and writing it on the next frame', () => {
    render(
      <AnnouncerProvider>
        <Speaker message="Updated" />
      </AnnouncerProvider>,
    );
    const status = screen.getByRole('status');

    act(() => screen.getByRole('button').click());
    nextFrame();
    expect(status).toHaveTextContent('Updated');

    act(() => screen.getByRole('button').click());
    expect(status).toBeEmptyDOMElement();
    nextFrame();
    expect(status).toHaveTextContent('Updated');
  });

  it('[frontend_i18n.AC-12] nested providers reuse the outer regions instead of creating new ones', () => {
    render(
      <AnnouncerProvider>
        <AnnouncerProvider>
          <Speaker message="Hello" />
        </AnnouncerProvider>
      </AnnouncerProvider>,
    );

    expect(screen.getAllByRole('status')).toHaveLength(1);
    expect(screen.getAllByRole('alert')).toHaveLength(1);
    act(() => screen.getByRole('button').click());
    nextFrame();
    expect(screen.getByRole('status')).toHaveTextContent('Hello');
  });

  it('[frontend_i18n.AC-12] useAnnounce outside the provider fails loudly', () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined);

    expect(() => renderHook(() => useAnnounce())).toThrow(/AnnouncerProvider/);
  });

  it('works with renderHook inside the provider', () => {
    const wrapper = ({ children }: { children: ReactNode }) => (
      <AnnouncerProvider>{children}</AnnouncerProvider>
    );

    const { result } = renderHook(() => useAnnounce(), { wrapper });

    expect(typeof result.current).toBe('function');
  });
});
