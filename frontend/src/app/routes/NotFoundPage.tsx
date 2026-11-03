import { useTranslation } from 'react-i18next';

import { LinkButton } from '../../shared/ui/LinkButton';
import { usePageTitle } from '../../shared/ui/usePageTitle';

/** Any unknown route (passenger_stop_view.AC-20). */
export function NotFoundPage() {
  const { t } = useTranslation();
  usePageTitle(t('notFound.title'));

  return (
    <div className="flex flex-col items-start gap-5">
      <h1 className="text-[1.75rem] leading-[1.15] font-bold">{t('notFound.title')}</h1>
      <p className="text-lg">{t('notFound.body')}</p>
      <LinkButton to="/">{t('notFound.home')}</LinkButton>
    </div>
  );
}
