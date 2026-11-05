import { useState } from 'react';
import { Trans, useTranslation } from 'react-i18next';

import { getLastStop } from '../../features/passenger/stop/lastStop';
import { gtfsLang } from '../../features/passenger/stop/useUiLanguage';
import { LinkButton } from '../../shared/ui/LinkButton';
import { usePageTitle } from '../../shared/ui/usePageTitle';

/** Landing page at `/`: passengers reach their stop by scanning its QR code (CU-01). */
export function HomePage() {
  const { t, i18n } = useTranslation();
  usePageTitle(t('home.title'));
  // Last stop opened on this device (passenger_stop_view.AC-19).
  const [lastStop] = useState(getLastStop);

  return (
    <div className="flex flex-col gap-5">
      <h1 className="text-[1.75rem] leading-[1.15] font-bold">{t('app.name')}</h1>
      <p className="text-lg">{t('app.tagline')}</p>
      <p>{t('home.scanQr')}</p>
      {lastStop !== null && (
        <LinkButton
          to={`/p/${encodeURIComponent(lastStop.stopId)}?t=${encodeURIComponent(lastStop.token)}`}
          className="self-start py-2 text-left"
        >
          <span>
            <Trans
              i18nKey="home.lastStop"
              values={{ name: lastStop.name }}
              components={{
                name: <span lang={gtfsLang(i18n.language === 'ca' ? 'ca' : 'es')} />,
              }}
            />
          </span>
        </LinkButton>
      )}
      {/* Accessibility profile kept on the device (passenger_alert_ui.AC-02, CU-05). */}
      <LinkButton to="/necesidades" className="self-start">
        {t('home.needsLink')}
      </LinkButton>
    </div>
  );
}
