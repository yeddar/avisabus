/** Test helpers for the stop view components. */

/** Text for screen readers of an arrival row (its visually hidden sentence). */
export function spokenText(item: HTMLElement): string {
  const hidden = item.querySelector('.sr-only');
  return hidden?.textContent ?? '';
}

/** Visible content of an arrival row (hidden from screen readers to avoid reading it twice). */
export function visualPart(item: HTMLElement): HTMLElement {
  const visual = item.querySelector<HTMLElement>('[aria-hidden="true"]');
  if (visual === null) throw new Error('arrival row without visual part');
  return visual;
}
