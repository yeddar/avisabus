import type { HTMLAttributes, ReactNode } from 'react';

/** Text for assistive technologies only. */
export function VisuallyHidden({
  children,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { children?: ReactNode }) {
  return (
    <span className="sr-only" {...props}>
      {children}
    </span>
  );
}
