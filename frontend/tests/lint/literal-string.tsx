// Invalid on purpose: used by src/__tests__/eslint-i18n.test.ts (frontend_i18n.AC-07).
// Ignored by `npm run lint`. Each element below holds exactly one untranslated literal.
export function LiteralStrings() {
  return (
    <div>
      <p>Texto sin traducir</p>
      <button type="button" aria-label="Cerrar" />
      <img src="/icons/icon-192.png" alt="Autobús" />
      <span title="Título literal" />
      <input aria-label={undefined} placeholder="Escribe aquí" />
      <div aria-description="Descripción literal" />
      <a href="/" aria-label="Inicio" />
      <a href="/" title="Ir al inicio" />
      <svg aria-label="Autobús" />
    </div>
  );
}
