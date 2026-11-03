import { useTranslation } from 'react-i18next';

import type { StopLine, StopResponse } from '../../../shared/api/types';
import { GtfsText } from '../../../shared/i18n/GtfsText';
import { VisuallyHidden } from '../../../shared/ui/VisuallyHidden';
import { LineBadge } from './LineBadge';

/** One badge per line: the API lists each direction of a line separately. */
function distinctLines(lines: StopLine[]): StopLine[] {
  const seen = new Set<string>();
  return lines.filter(({ line }) => !seen.has(line) && seen.add(line) !== undefined);
}

/**
 * Stop name (h1, as in the GTFS), code and lines that serve it (passenger_stop_view.AC-04,
 * docs/design.md §3 and §5.2).
 */
export function StopHeader({ stop }: { stop: StopResponse }) {
  const { t } = useTranslation();

  return (
    <>
      <div className="flex flex-col gap-1">
        <h1 className="text-[1.75rem] leading-[1.15] font-bold">
          <GtfsText>{stop.name}</GtfsText>
        </h1>
        <p className="text-text-muted">{t('stop.code', { code: stop.stop_id })}</p>
      </div>
      <section aria-labelledby="lines-h" className="flex flex-col gap-2">
        <h2
          id="lines-h"
          className="text-[0.9375rem] font-bold tracking-[0.04em] text-text-muted uppercase"
        >
          {t('stop.lines')}
        </h2>
        {/* role="list" keeps the list semantics in Safari/VoiceOver (list-style: none). */}
        {/* eslint-disable-next-line jsx-a11y/no-redundant-roles */}
        <ul role="list" className="flex flex-wrap gap-2">
          {distinctLines(stop.lines).map((line) => (
            <li key={line.line}>
              <VisuallyHidden>{t('stop.lineName', { line: line.line })}</VisuallyHidden>
              <span aria-hidden="true">
                <LineBadge
                  line={line.line}
                  color={line.color}
                  textColor={line.text_color}
                  size="list"
                />
              </span>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
