import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { I18nextProvider } from 'react-i18next';

import { App } from './app/App';
import { initI18n } from './shared/i18n/i18n';
import './index.css';

const container = document.getElementById('root');
if (container === null) {
  throw new Error('Root element #root not found');
}

const i18n = initI18n();

createRoot(container).render(
  <StrictMode>
    <I18nextProvider i18n={i18n}>
      <App />
    </I18nextProvider>
  </StrictMode>,
);
