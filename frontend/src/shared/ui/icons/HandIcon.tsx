/** Raised hand icon of the "Solicitar" action (docs/design.md §5.8 and §6): stroke, decorative. */
export function HandIcon({ className }: { className?: string }) {
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
      <path d="M8 13V5.5a1.5 1.5 0 0 1 3 0V11" />
      <path d="M11 10.5V4a1.5 1.5 0 0 1 3 0v6.5" />
      <path d="M14 10.5V5.5a1.5 1.5 0 0 1 3 0V12" />
      <path d="M17 12V9a1.5 1.5 0 0 1 3 0v5a8 8 0 0 1-8 8h-.6a6.5 6.5 0 0 1-5.1-2.5L3.6 16a1.6 1.6 0 0 1 2.5-2L8 15.5" />
    </svg>
  );
}
