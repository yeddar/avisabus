const SILHOUETTES = 3;

/**
 * Three passenger silhouettes, 40 × 18 px (docs/design.md §4 and §5.4): `filled` of them are
 * filled and the rest outlined. Decorative: the level is always given as text too.
 */
export function OccupancyIcon({ filled }: { filled: number }) {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      viewBox="0 0 40 18"
      width={40}
      height={18}
      className="shrink-0"
    >
      {Array.from({ length: SILHOUETTES }, (_, index) => {
        const isFilled = index < filled;
        return (
          <g
            key={index}
            data-silhouette={isFilled ? 'filled' : 'outline'}
            transform={`translate(${1 + index * 13} 0)`}
            fill={isFilled ? 'currentColor' : 'none'}
            stroke="currentColor"
            strokeWidth={1.5}
            strokeLinejoin="round"
          >
            <circle cx={6} cy={4.25} r={3.25} />
            <path d="M1 17v-2.5a5 5 0 0 1 10 0V17z" />
          </g>
        );
      })}
    </svg>
  );
}
