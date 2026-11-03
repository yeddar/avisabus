import { useTranslation } from 'react-i18next';
import { Outlet } from 'react-router-dom';

import { LanguageSelector } from '../shared/i18n/LanguageSelector';
import { AnnouncerProvider } from '../shared/ui/Announcer';
import { MAIN_CONTENT_ID, SkipLink } from '../shared/ui/SkipLink';
import { BusIcon } from '../shared/ui/icons/BusIcon';

/** Content column shared by header, main and footer (docs/design.md §2 principle 5 and §5.1). */
const COLUMN = 'mx-auto w-full max-w-[640px] px-4';

/** Accessible page structure shared by every view (frontend_i18n.AC-10, AC-04, AC-14). */
export function Layout() {
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
          <Outlet />
        </main>
        <footer className="border-t border-divider">
          <p className={`${COLUMN} py-4 text-[13px] text-text-muted`}>{t('layout.attribution')}</p>
        </footer>
      </div>
    </AnnouncerProvider>
  );
}
