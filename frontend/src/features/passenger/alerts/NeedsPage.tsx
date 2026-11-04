import { type FormEvent, useState } from 'react';
import { useTranslation } from 'react-i18next';

import {
  clearNeedsProfile,
  getNeedsProfile,
  setNeedsProfile,
  type Need,
} from '../../../shared/device/needsProfile';
import { useAnnounce } from '../../../shared/ui/Announcer';
import { Button } from '../../../shared/ui/Button';
import { usePageTitle } from '../../../shared/ui/usePageTitle';
import { NeedsFieldset } from './NeedsFieldset';

/**
 * Route /necesidades, "Mis necesidades" (CU-05, passenger_alert_ui.AC-02): the profile is kept
 * only on this device and preloaded in the request dialog. Nothing is sent to the server.
 */
export function NeedsPage() {
  const { t } = useTranslation();
  const announce = useAnnounce();
  const [needs, setNeeds] = useState<Need[]>(getNeedsProfile);
  usePageTitle(t('needsPage.title'));

  function save(event: FormEvent) {
    event.preventDefault();
    setNeedsProfile(needs);
    announce(t('needsPage.saved'), 'polite');
  }

  function clear() {
    clearNeedsProfile();
    setNeeds([]);
    announce(t('needsPage.cleared'), 'polite');
  }

  return (
    <div className="flex flex-col gap-5">
      <h1 className="text-[1.75rem] leading-[1.15] font-bold">{t('needsPage.title')}</h1>
      <p>{t('needsPage.intro')}</p>
      <form onSubmit={save} className="flex flex-col gap-5">
        <NeedsFieldset value={needs} onChange={setNeeds} />
        <div className="flex flex-col gap-3">
          <Button type="submit" variant="primary" className="min-h-12 w-full">
            {t('needsPage.save')}
          </Button>
          <Button onClick={clear} className="min-h-12 w-full">
            {t('needsPage.clear')}
          </Button>
        </div>
      </form>
    </div>
  );
}
