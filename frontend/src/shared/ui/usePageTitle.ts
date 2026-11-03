import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

const APP_NAME = 'AvisaBus';

/** Key of the last location a view announced itself for; null until the first view mounts. */
let lastLocationKey: string | null = null;

/** Test isolation only: forget the navigation history of previous renders. */
export function resetPageTitleTracking(): void {
  lastLocationKey = null;
}

/**
 * Sets `document.title` to "<title> · AvisaBus" and, after an in-app navigation (not on the
 * initial load), moves the focus to the view's h1 (frontend_i18n.AC-11).
 */
export function usePageTitle(title: string): void {
  const { key } = useLocation();

  useEffect(() => {
    document.title = `${title} · ${APP_NAME}`;
  }, [title]);

  useEffect(() => {
    const previous = lastLocationKey;
    lastLocationKey = key;
    // Initial load, or the same location mounted again (e.g. React StrictMode): keep the focus.
    if (previous === null || previous === key) return;
    const heading = document.querySelector<HTMLHeadingElement>('main h1');
    if (heading === null) return;
    heading.tabIndex = -1;
    heading.focus();
  }, [key]);
}
