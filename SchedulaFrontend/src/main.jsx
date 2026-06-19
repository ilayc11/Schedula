import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from "react-router-dom";
import { MockModeProvider } from './context/MockModeContext.jsx';
import './index.css'
import App from './App.jsx'
import { installSessionExpiryInterceptor } from './utils/sessionExpiry.js'

// Catch expired/invalid auth tokens globally and redirect to login with a
// friendly message instead of leaking raw fetch errors across pages.
installSessionExpiryInterceptor();

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <MockModeProvider>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </MockModeProvider>
  </StrictMode>,
)
