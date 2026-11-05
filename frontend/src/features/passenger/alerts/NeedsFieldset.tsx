import { useTranslation } from 'react-i18next';

import { NEEDS, type Need } from '../../../shared/device/needsProfile';

export interface NeedsFieldsetProps {
  /** Checked needs. */
  value: readonly Need[];
  onChange: (needs: Need[]) => void;
  disabled?: boolean;
}

/** Shared look of a checkbox row (docs/design.md §5.8): 24 px box, 16 px text, ≥ 48 px row. */
export const CHECKBOX_ROW = 'flex min-h-12 cursor-pointer items-center gap-3 text-base';
export const CHECKBOX = 'size-6 shrink-0 cursor-pointer accent-accent';

/**
 * The four accessibility needs (RF-17) as checkboxes, in canonical order, grouped under the
 * legend "¿Necesitas algo al subir?". Used by the request dialog and by "Mis necesidades".
 */
export function NeedsFieldset({ value, onChange, disabled = false }: NeedsFieldsetProps) {
  const { t } = useTranslation();

  function toggle(need: Need, checked: boolean) {
    onChange(NEEDS.filter((item) => (item === need ? checked : value.includes(item))));
  }

  return (
    <fieldset className="flex flex-col" disabled={disabled}>
      <legend className="mb-1 text-base font-bold">{t('alert.needsLegend')}</legend>
      {NEEDS.map((need) => (
        <label key={need} className={CHECKBOX_ROW}>
          <input
            type="checkbox"
            className={CHECKBOX}
            checked={value.includes(need)}
            onChange={(event) => toggle(need, event.target.checked)}
          />
          {t(`needs.${need}`)}
        </label>
      ))}
    </fieldset>
  );
}
