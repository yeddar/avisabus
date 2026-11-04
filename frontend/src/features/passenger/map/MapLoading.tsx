import { useTranslation } from 'react-i18next';

/**
 * Shown while the map chunk loads (passenger_map_view.AC-02). It is part of the initial bundle,
 * so it must not import the map nor Leaflet.
 */
export function MapLoading() {
  const { t } = useTranslation();
  return (
    <p role="status" className="text-lg text-text-muted">
      {t('map.loading')}
    </p>
  );
}
