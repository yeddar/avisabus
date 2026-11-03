import { useTranslation } from 'react-i18next';

import { toHtmlLang } from './languages';

/**
 * Stop, line and destination names from the GTFS/SAE: never translated (RF-32) and marked as
 * Valencian when the interface is in Spanish, so screen readers pronounce them correctly.
 */
export function GtfsText({ children, as = 'span' }: { children: string; as?: 'span' | 'strong' }) {
  const { i18n } = useTranslation();
  const Tag = as;
  const lang = i18n.language === 'es' ? toHtmlLang('ca') : undefined;
  return <Tag lang={lang}>{children}</Tag>;
}
