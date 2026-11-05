import { useQueryClient } from '@tanstack/react-query';
import { type FormEvent, useEffect, useRef, useState } from 'react';
import { Trans, useTranslation } from 'react-i18next';

import type { Arrival, CreateAlertRequest } from '../../../shared/api/types';
import { getNeedsProfile, setNeedsProfile, type Need } from '../../../shared/device/needsProfile';
import { Button } from '../../../shared/ui/Button';
import { spokenDestination } from '../stop/destination';
import { spokenArrivalTime } from '../stop/spokenTime';
import { gtfsLang, useUiLanguage } from '../stop/useUiLanguage';
import { type CreateError, useAlerts } from './AlertsProvider';
import { CHECKBOX, CHECKBOX_ROW, NeedsFieldset } from './NeedsFieldset';

/** Minutes shown with a 429 that has no usable Retry-After: the rate limit window (alert_create.AC-08). */
export const RATE_FALLBACK_MIN = 10;

const SECONDS_PER_MINUTE = 60;

type DialogError = { error: CreateError; retryAfterS?: number | null };

export interface RequestDialogProps {
  arrival: Arrival;
  /** Everything POST /alerts needs except the needs (the bus of the card, AC-05). */
  request: Omit<CreateAlertRequest, 'needs'>;
  now: Date;
  scheduled: boolean;
  /** The dialog was closed without requesting (Escape or "Volver"). */
  onDismiss: () => void;
}

function ErrorMessage({ error }: { error: DialogError }) {
  const { t } = useTranslation();
  switch (error.error) {
    case 'gone':
      return t('alert.error.gone');
    case 'rate': {
      const seconds = error.retryAfterS;
      const count =
        seconds === null || seconds === undefined
          ? RATE_FALLBACK_MIN
          : Math.max(1, Math.ceil(seconds / SECONDS_PER_MINUTE));
      return t('alert.error.rate', { count });
    }
    case 'notFound':
      return t('alert.error.notFound');
    case 'network':
      return t('alert.error.network');
  }
}

/**
 * Confirmation of a stop request (passenger_alert_ui.AC-04 … AC-06, docs/design.md §5.8): a
 * modal <dialog> (the browser traps the focus and handles Escape) with the arrival time, the
 * needs preloaded from the profile, "Recordar…", "Solicitar parada" and "Volver". The focus
 * starts on the title; errors keep the dialog open with a focused role="alert" message.
 */
export function RequestDialog({ arrival, request, now, scheduled, onDismiss }: RequestDialogProps) {
  const { t } = useTranslation();
  const language = useUiLanguage();
  const queryClient = useQueryClient();
  const { create } = useAlerts();
  const dialog = useRef<HTMLDialogElement>(null);
  const title = useRef<HTMLHeadingElement>(null);
  const errorMessage = useRef<HTMLParagraphElement>(null);
  const submitted = useRef(false);
  const mounted = useRef(true);
  const [needs, setNeeds] = useState<Need[]>(getNeedsProfile);
  const [remember, setRemember] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<DialogError | null>(null);

  useEffect(() => {
    mounted.current = true;
    const element = dialog.current;
    if (element !== null && !element.open) element.showModal();
    title.current?.focus();
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    if (error !== null) errorMessage.current?.focus();
  }, [error]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (sending) return;
    if (remember) setNeedsProfile(needs);
    setSending(true);
    setError(null);
    const outcome = await create({ ...request, needs });
    if (!mounted.current) return;
    if (outcome === 'ok') {
      // The provider announces it and moves the focus to "Cancelar solicitud" (AC-05).
      submitted.current = true;
      dialog.current?.close();
      return;
    }
    setSending(false);
    setError(outcome);
    if (outcome.error === 'gone') {
      void queryClient.invalidateQueries({ queryKey: ['arrivals', request.stop_id] });
    }
  }

  return (
    <dialog
      ref={dialog}
      aria-labelledby="req-title"
      onCancel={(event) => {
        // Escape while the request is in flight would lose its answer.
        if (sending) event.preventDefault();
      }}
      onClose={() => {
        if (!submitted.current) onDismiss();
      }}
      className={
        'fixed inset-x-0 top-auto bottom-0 m-0 max-h-[90dvh] w-full max-w-none overflow-y-auto ' +
        'rounded-t-[14px] border-0 bg-surface p-5 text-text backdrop:bg-[rgba(20,23,31,0.5)] ' +
        'sm:inset-0 sm:m-auto sm:h-fit sm:max-w-[480px] sm:rounded-[14px]'
      }
    >
      <form onSubmit={(event) => void submit(event)} className="flex flex-col gap-4">
        <h2 id="req-title" ref={title} tabIndex={-1} className="text-[1.375rem] font-bold">
          <Trans
            i18nKey="alert.dialogTitle"
            values={{ line: arrival.line, destination: spokenDestination(arrival) }}
            components={{ destination: <span lang={gtfsLang(language)} /> }}
          />
        </h2>
        <p>
          {t('alert.arrivalInfo', {
            time: spokenArrivalTime(arrival, now, scheduled, t, language),
          })}
        </p>
        <NeedsFieldset value={needs} onChange={setNeeds} disabled={sending} />
        <label className={CHECKBOX_ROW}>
          <input
            type="checkbox"
            className={CHECKBOX}
            checked={remember}
            disabled={sending}
            onChange={(event) => setRemember(event.target.checked)}
          />
          {t('alert.remember')}
        </label>
        {error !== null && (
          <p
            ref={errorMessage}
            role="alert"
            tabIndex={-1}
            className="rounded-[10px] border-2 border-occ-full-fg bg-occ-full-bg p-3 font-bold text-occ-full-fg"
          >
            <ErrorMessage error={error} />
          </p>
        )}
        <div className="flex flex-col gap-3">
          <Button type="submit" variant="primary" disabled={sending} className="min-h-12 w-full">
            {t(sending ? 'alert.sending' : 'alert.confirm')}
          </Button>
          <Button
            disabled={sending}
            onClick={() => dialog.current?.close()}
            className="min-h-12 w-full"
          >
            {t('alert.back')}
          </Button>
        </div>
      </form>
    </dialog>
  );
}
