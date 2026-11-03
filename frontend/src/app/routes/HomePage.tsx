// Temporary literal heading: frontend_i18n T-07 replaces it with a translation key.
export function HomePage() {
  return (
    <main className="mx-auto max-w-screen-md p-4">
      {/* eslint-disable-next-line i18next/no-literal-string -- removed in frontend_i18n T-07 */}
      <h1 className="text-2xl font-bold">AvisaBus</h1>
    </main>
  );
}
