import { useTranslation } from 'react-i18next';

import { LinkButton } from '../../../shared/ui/LinkButton';
import { usePageTitle } from '../../../shared/ui/usePageTitle';

/**
 * Unknown stop, invalid token or no token (passenger_stop_view.AC-16): asks to scan the stop's
 * QR again and never shows the stop id or the token of the URL.
 */
export function StopNotFound() {
  const { t } = useTranslation();
  usePageTitle(t('stop.notFound.title'));

  return (
    <div className="flex flex-col items-start gap-5">
      <h1 className="text-[1.75rem] leading-[1.15] font-bold">{t('stop.notFound.title')}</h1>
      <p className="text-lg">{t('stop.notFound.body')}</p>
      <LinkButton to="/">{t('notFound.home')}</LinkButton>
    </div>
  );
}
