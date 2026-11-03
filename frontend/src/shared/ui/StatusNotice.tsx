import type { ReactNode } from 'react';

import { InfoIcon } from './icons/InfoIcon';

export interface StatusNoticeProps {
  children: ReactNode;
  /** `status` for notices that screen readers must hear when they appear. */
  role?: 'status';
  /** Optional controls under the text (e.g. a retry button). */
  action?: ReactNode;
}

/**
 * Status notice of docs/design.md §5.6: accent-surface box with a 2 px accent border, radius
 * 12 px, information icon and 16 px text whose first sentence is bold (given as <strong>).
 */
export function StatusNotice({ children, role, action }: StatusNoticeProps) {
  return (
    <div
      role={role}
      className="flex gap-2.5 rounded-xl border-2 border-accent bg-accent-surface p-3 text-base text-text"
    >
      <InfoIcon className="mt-0.5 size-5 shrink-0 text-accent" />
      <div className="flex min-w-0 flex-col items-start gap-3">
        <p>{children}</p>
        {action}
      </div>
    </div>
  );
}
