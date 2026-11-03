export type ButtonVariant = 'primary' | 'secondary';

/** Shared look of Button and LinkButton: docs/design.md §5.5, 44 × 44 px minimum target. */
const BASE =
  'inline-flex min-h-11 min-w-11 items-center justify-center gap-2 rounded-[10px] border-2 ' +
  'border-accent px-4 text-base font-bold no-underline transition-colors ' +
  'hover:border-accent-hover disabled:cursor-not-allowed';

const VARIANTS: Record<ButtonVariant, string> = {
  primary: 'bg-accent text-white hover:bg-accent-hover',
  secondary: 'bg-surface text-accent hover:text-accent-hover',
};

export function buttonClassName(variant: ButtonVariant, extra?: string): string {
  return [BASE, VARIANTS[variant], extra].filter(Boolean).join(' ');
}
