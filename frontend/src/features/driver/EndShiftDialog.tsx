import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';

import { Button } from '../../shared/ui/Button';

export interface EndShiftDialogProps {
  onConfirm: () => void;
  onCancel: () => void;
}

/**
 * Confirmation of the end of the shift (driver_ui.AC-10): a modal <dialog> (the browser traps the
 * focus and handles Escape, which counts as "Seguir"). The focus starts on the title.
 */
export function EndShiftDialog({ onConfirm, onCancel }: EndShiftDialogProps) {
  const { t } = useTranslation();
  const dialog = useRef<HTMLDialogElement>(null);
  const title = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    const element = dialog.current;
    if (element !== null && !element.open) element.showModal();
    title.current?.focus();
  }, []);

  return (
    <dialog
      ref={dialog}
      aria-labelledby="end-shift-title"
      onClose={onCancel}
      className="m-auto w-full max-w-[480px] rounded-[14px] border-0 bg-surface p-5 text-text backdrop:bg-[rgba(20,23,31,0.5)]"
    >
      <div className="flex flex-col gap-4">
        <h2 id="end-shift-title" ref={title} tabIndex={-1} className="text-[1.375rem] font-bold">
          {t('driver.end.confirm')}
        </h2>
        <div className="flex flex-col gap-3">
          <Button variant="primary" className="min-h-12 w-full" onClick={onConfirm}>
            {t('driver.end.yes')}
          </Button>
          <Button className="min-h-12 w-full" onClick={onCancel}>
            {t('driver.end.no')}
          </Button>
        </div>
      </div>
    </dialog>
  );
}
