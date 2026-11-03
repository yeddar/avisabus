import { useTranslation } from 'react-i18next';

import { usePageTitle } from '../../shared/ui/usePageTitle';

/** Landing page at `/`: passengers reach their stop by scanning its QR code (CU-01). */
export function HomePage() {
  const { t } = useTranslation();
  usePageTitle(t('home.title'));

  return (
    <div className="flex flex-col gap-5">
      <h1 className="text-[1.75rem] leading-[1.15] font-bold">{t('app.name')}</h1>
      <p className="text-lg">{t('app.tagline')}</p>
      <p>{t('home.scanQr')}</p>
    </div>
  );
}
