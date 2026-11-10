import type { Need } from '../../../shared/device/needsProfile';

/** Drawing of each accessibility need (docs/design.md §5.9 and §6). */
function paths(need: Need) {
  switch (need) {
    case 'RAMP':
      return <path d="M3 19h18L3 9z" />;
    case 'EXTRA_TIME':
      return (
        <>
          <circle cx="12" cy="12" r="9.5" />
          <path d="M12 7v5l3 2" />
        </>
      );
    case 'SEAT':
      return <path d="M7 4v11h9l1 5M7 15l-1 5M7 10h7" />;
    case 'VISUAL':
      return (
        <>
          <path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z" />
          <circle cx="12" cy="12" r="3" />
        </>
      );
  }
}

/** Decorative icon of a need; the text next to it always says which one it is. */
export function NeedIcon({ need, className }: { need: Need; className?: string }) {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      {paths(need)}
    </svg>
  );
}
