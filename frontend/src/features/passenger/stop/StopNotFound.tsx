import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';

import { LinkButton } from '../../../shared/ui/LinkButton';
import { usePageTitle } from '../../../shared/ui/usePageTitle';

interface StopNotFoundProps {
  /**
   * The 404 answered a manual "Actualizar" or "Reintentar": the focused button is gone, so the
   * focus goes to the h1, which is read on receiving it (passenger_stop_view.AC-24).
   */
  focusHeading?: boolean;
}

/**
 * Unknown stop, invalid token or no token (passenger_stop_view.AC-16): asks to scan the stop's
 * QR again and never shows the stop id or the token of the URL.
 */
export function StopNotFound({ focusHeading = false }: StopNotFoundProps) {
  const { t } = useTranslation();
  const heading = useRef<HTMLHeadingElement>(null);
  usePageTitle(t('stop.notFound.title'));

  useEffect(() => {
    if (focusHeading) heading.current?.focus();
  }, [focusHeading]);

  return (
    <div className="flex flex-col items-start gap-5">
      <h1 ref={heading} tabIndex={-1} className="text-[1.75rem] leading-[1.15] font-bold">
        {t('stop.notFound.title')}
      </h1>
      <p className="text-lg">{t('stop.notFound.body')}</p>
      <LinkButton to="/">{t('notFound.home')}</LinkButton>
    </div>
  );
}
