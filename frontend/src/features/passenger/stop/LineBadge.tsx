import { accessibleLineColors } from '../../../shared/color/contrast';

export interface LineBadgeProps {
  line: string;
  color: string | null;
  textColor: string | null;
  /** `card`: in an arrival card (40 px high); `list`: in the list of lines (36 px). */
  size?: 'card' | 'list';
}

const SIZES = {
  card: 'h-10 min-w-[3.25rem] text-[1.375rem]',
  list: 'h-9 min-w-12 text-xl',
} as const;

/**
 * Line badge of docs/design.md §5.2 with the GTFS line colours, corrected to 4.5:1
 * (passenger_stop_view.AC-11). The line number is shown as it comes from the GTFS.
 */
export function LineBadge({ line, color, textColor, size = 'card' }: LineBadgeProps) {
  const { bg, fg } = accessibleLineColors(color, textColor);
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center rounded-lg px-2 leading-none font-bold ${SIZES[size]}`}
      style={{ backgroundColor: bg, color: fg }}
    >
      {line}
    </span>
  );
}
