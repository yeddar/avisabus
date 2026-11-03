/** Bus pictogram for the logo (docs/design.md §6): own inline SVG, stroke, decorative. */
export function BusIcon({ className }: { className?: string }) {
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
      <rect x="4" y="3" width="16" height="15" rx="3" />
      <path d="M4 11h16" />
      <path d="M8 7h8" />
      <path d="M7 18v2.5" />
      <path d="M17 18v2.5" />
      <circle cx="8" cy="14.5" r="0.6" fill="currentColor" />
      <circle cx="16" cy="14.5" r="0.6" fill="currentColor" />
    </svg>
  );
}
