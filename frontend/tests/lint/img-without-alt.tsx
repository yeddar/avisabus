// Invalid on purpose: used by src/__tests__/eslint-a11y.test.ts (AC-15). Ignored by `npm run lint`.
export function ImageWithoutAlt() {
  return <img src="/icons/icon-192.png" />;
}
