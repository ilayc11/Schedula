// src/utils/sessionExpiry.js
//
// Global handling for expired/invalid auth tokens.
//
// Every page in the app calls `fetch` directly with a Bearer token from
// localStorage. When that token expires the backend replies 401, which would
// otherwise surface as a raw "Failed to fetch"/"Request failed (401)" error in
// each page. Instead of patching every caller, we wrap `window.fetch` once at
// startup: on a 401 we clear the stale session and send the user back to the
// login screen with a friendly "your session expired" message.

const SESSION_MESSAGE_KEY = "session_message";

// Guard so several in-flight requests failing at once only trigger one redirect.
let isHandlingExpiry = false;

function clearSession() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("user_data");
}

function redirectToLogin() {
  // Hard navigation resets all in-memory React state, so no stale page is left
  // showing error toasts behind the login screen.
  if (window.location.pathname !== "/login") {
    window.location.assign("/login");
  }
}

/**
 * Read and clear the one-shot session message (e.g. "your session expired").
 * The login page calls this on mount to show a friendly banner.
 */
export function consumeSessionMessage() {
  const message = sessionStorage.getItem(SESSION_MESSAGE_KEY);
  if (message) sessionStorage.removeItem(SESSION_MESSAGE_KEY);
  return message;
}

/**
 * Handle an authentication failure: stash a friendly message, drop the stale
 * session, and bounce to the login page. Safe to call from multiple places;
 * only the first call in a burst takes effect.
 */
export function handleSessionExpired() {
  if (isHandlingExpiry) return;
  isHandlingExpiry = true;
  sessionStorage.setItem(
    SESSION_MESSAGE_KEY,
    "Your session has expired. Please log in again."
  );
  clearSession();
  redirectToLogin();
}

/**
 * Install the global fetch interceptor. Call once at app startup.
 */
export function installSessionExpiryInterceptor() {
  if (typeof window === "undefined" || window.__sessionExpiryInstalled) return;
  window.__sessionExpiryInstalled = true;

  const originalFetch = window.fetch.bind(window);

  window.fetch = async (...args) => {
    const response = await originalFetch(...args);

    if (response.status === 401) {
      // Don't react to the login request itself failing (bad credentials):
      // the login page shows its own inline error and there's no session yet.
      const isLoginRequest =
        window.location.pathname === "/login" ||
        !localStorage.getItem("access_token");

      if (!isLoginRequest) {
        handleSessionExpired();
      }
    }

    return response;
  };
}
