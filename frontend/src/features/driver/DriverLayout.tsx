import { Suspense } from 'react';
import { useTranslation } from 'react-i18next';
import { Outlet } from 'react-router-dom';

import { LanguageSelector } from '../../shared/i18n/LanguageSelector';
import { AnnouncerProvider } from '../../shared/ui/Announcer';
import { BusIcon } from '../../shared/ui/icons/BusIcon';
import { MAIN_CONTENT_ID, SkipLink } from '../../shared/ui/SkipLink';

/** Wider than the passenger column: three cards side by side on a tablet (docs/design.md §5.9). */
const COLUMN = 'mx-auto w-full max-w-[1200px] px-4';

/** Page structure of the driver routes: the same landmarks as the passenger Layout. */
export function DriverLayout() {
  const { t } = useTranslation();

  return (
    <AnnouncerProvider>
      <div className="flex min-h-dvh flex-col bg-surface text-text">
        <SkipLink />
        <header className="border-b border-divider">
          <div className={`${COLUMN} flex flex-wrap items-center justify-between gap-3 py-3`}>
            <span className="flex items-center gap-2 text-xl font-bold text-accent">
              <BusIcon className="size-7 shrink-0" />
              {t('app.name')}
            </span>
            <LanguageSelector />
          </div>
        </header>
        <main id={MAIN_CONTENT_ID} tabIndex={-1} className={`${COLUMN} flex-1 pt-5 pb-8`}>
          <Suspense fallback={null}>
            <Outlet />
          </Suspense>
        </main>
        <footer className="border-t border-divider">
          <p className={`${COLUMN} py-4 text-[13px] text-text-muted`}>{t('layout.attribution')}</p>
        </footer>
      </div>
    </AnnouncerProvider>
  );
}
