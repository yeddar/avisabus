/** Bell of the "Silenciar tono" button (docs/design.md §6): crossed out while silenced. */
export function BellIcon({ muted, className }: { muted: boolean; className?: string }) {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2.2}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      <path d="M6 9a6 6 0 1 1 12 0c0 7 3 8 3 8H3s3-1 3-8" />
      <path d="M10 21a2 2 0 0 0 4 0" />
      {muted && <path d="M3 3l18 18" />}
    </svg>
  );
}
