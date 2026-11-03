import type { MouseEvent } from 'react';
import { useTranslation } from 'react-i18next';

export const MAIN_CONTENT_ID = 'main';

/** First focusable element of every view: hidden until focused, moves the focus to main. */
export function SkipLink() {
  const { t } = useTranslation();

  function skipToMain(event: MouseEvent<HTMLAnchorElement>) {
    const main = document.getElementById(MAIN_CONTENT_ID);
    if (main === null) return;
    // Focus explicitly instead of following the fragment, so the router URL is untouched.
    event.preventDefault();
    main.focus();
    main.scrollIntoView?.();
  }

  return (
    <a
      href={`#${MAIN_CONTENT_ID}`}
      onClick={skipToMain}
      className="sr-only z-50 min-h-11 min-w-11 bg-surface font-bold text-accent focus:not-sr-only focus:absolute focus:px-4 focus:top-2 focus:left-2 focus:inline-flex focus:items-center focus:rounded-[10px] focus:border-2 focus:border-accent"
    >
      {t('layout.skipToContent')}
    </a>
  );
}
