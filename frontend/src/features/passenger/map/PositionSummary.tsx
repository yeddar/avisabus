import { useId } from 'react';
import { useTranslation } from 'react-i18next';

import { GtfsText } from '../../../shared/i18n/GtfsText';
import { type Summary, summaryParts } from './summary';

export interface PositionSummaryProps {
  summary: Summary;
  /** Id of the summary text, so the map can refer to it. */
  textId: string;
}

/**
 * "Dónde está el autobús": the text alternative to the map, shown before it
 * (passenger_map_view.AC-04), with the "Posición estimada" / "Posición según horario" badge
 * (AC-05). Not a live region: refreshes update it silently (AC-06). Look of docs/design.md §5.7:
 * accent-surface box, 2 px accent border, radius 14 px, figures in bold.
 */
export function PositionSummary({ summary, textId }: PositionSummaryProps) {
  const { t } = useTranslation();
  const headingId = useId();

  return (
    <section
      aria-labelledby={headingId}
      className="flex flex-col items-start gap-2.5 rounded-[14px] border-2 border-accent bg-accent-surface p-3.5"
    >
      <h2 id={headingId} className="text-lg font-bold">
        {t('map.summaryTitle')}
      </h2>
      <span className="rounded-full bg-accent px-2.5 py-0.5 text-[0.8125rem] font-bold text-white">
        {t(summary.badge === 'scheduled' ? 'map.scheduled' : 'map.estimated')}
      </span>
      <p id={textId} className="text-base leading-snug">
        {summaryParts(summary.text).map((part, index) => {
          if (part.kind === 'strong') return <strong key={index}>{part.text}</strong>;
          if (part.kind === 'name') return <GtfsText key={index}>{part.text}</GtfsText>;
          return part.text;
        })}
      </p>
    </section>
  );
}
