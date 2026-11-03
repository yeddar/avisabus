/** Information icon of the status notices (docs/design.md §5.6 and §6): stroke, decorative. */
export function InfoIcon({ className }: { className?: string }) {
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
      <circle cx="12" cy="12" r="9.5" />
      <path d="M12 11v6" />
      <circle cx="12" cy="7.5" r="0.6" fill="currentColor" />
    </svg>
  );
}
