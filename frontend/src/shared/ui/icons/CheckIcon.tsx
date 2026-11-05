/** Check mark icon of the request status box (docs/design.md §5.8): stroke, decorative. */
export function CheckIcon({ className }: { className?: string }) {
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
      <path d="m7.5 12.5 3 3 6-6.5" />
    </svg>
  );
}
