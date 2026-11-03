import type { ReactNode } from 'react';

/** Decorative 18 px icon slot shown before a button's visible text (docs/design.md §5.5). */
export function ButtonIcon({ children }: { children: ReactNode }) {
  return (
    <span aria-hidden="true" className="inline-flex size-[18px] shrink-0 items-center">
      {children}
    </span>
  );
}
