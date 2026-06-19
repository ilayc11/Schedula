import React, { useState, useEffect, useCallback, useRef } from "react";
import "./TelegramLinkingCard.css";

const POLL_INTERVAL_MS = 2500;
const POLL_TIMEOUT_MS = 120000;

function TelegramLinkingCard() {
  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
  const LECTURER_PREFIX = import.meta.env.VITE_API_PREFIX_LECTURER || "/lecturer";
  const API_BASE = API_BASE_URL + LECTURER_PREFIX;

  const [isLinked, setIsLinked] = useState(false);
  const [isWaitingForLink, setIsWaitingForLink] = useState(false);
  const [telegramLink, setTelegramLink] = useState("");
  const [statusMessage, setStatusMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const pollTimerRef = useRef(null);
  const pollingStartedAtRef = useRef(null);

  const getAuthHeaders = () => {
    const token = localStorage.getItem("access_token");
    const headers = {
      "Content-Type": "application/json",
    };

    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }

    return headers;
  };

  const stopPolling = useCallback(() => {
    if (pollTimerRef.current) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    pollingStartedAtRef.current = null;
  }, []);

  const getResponseErrorMessage = useCallback(async (res) => {
    try {
      const data = await res.json();
      if (typeof data?.detail === "string" && data.detail.trim()) {
        return data.detail;
      }
    } catch {
      // Ignore JSON parse failures and fall back to status-based error.
    }

    return `Error ${res.status}`;
  }, []);

  const applyStatus = useCallback((data) => {
    const linked = Boolean(data?.is_linked);
    const linkInProgress = Boolean(data?.link_in_progress);

    setIsLinked(linked);
    setTelegramLink(data?.telegram_link || "");

    if (linked) {
      setIsWaitingForLink(false);
      setStatusMessage("Connected. You will now receive Telegram notifications.");
      return;
    }

    if (linkInProgress) {
      setIsWaitingForLink(true);
      setStatusMessage("Waiting for Telegram confirmation. Tap Start in the bot.");
      return;
    }

    setIsWaitingForLink(false);
    setStatusMessage("");
  }, []);

  const fetchTelegramStatus = useCallback(async (showLoading = false) => {
    if (showLoading) {
      setIsLoading(true);
    }

    try {
      const token = localStorage.getItem("access_token");
      if (!token) {
        stopPolling();
        setIsWaitingForLink(false);
        setErrorMessage("Not authenticated.");
        return null;
      }

      const res = await fetch(`${API_BASE}/notifications/telegram-link/status`, {
        method: "GET",
        headers: getAuthHeaders(),
      });

      if (!res.ok) {
        const message = await getResponseErrorMessage(res);
        throw new Error(message);
      }

      const data = await res.json();
      applyStatus(data);
      setErrorMessage("");
      return data;
    } catch (err) {
      setErrorMessage(err?.message || "Failed to load Telegram status.");
      return null;
    } finally {
      if (showLoading) {
        setIsLoading(false);
      }
    }
  }, [API_BASE, applyStatus, getResponseErrorMessage, stopPolling]);

  const startPollingForLink = useCallback(() => {
    if (pollTimerRef.current) {
      return;
    }

    pollingStartedAtRef.current = Date.now();
    pollTimerRef.current = setInterval(async () => {
      const status = await fetchTelegramStatus(false);
      if (status?.is_linked) {
        stopPolling();
        return;
      }

      if (pollingStartedAtRef.current && Date.now() - pollingStartedAtRef.current > POLL_TIMEOUT_MS) {
        stopPolling();
        setIsWaitingForLink(false);
        setStatusMessage("Still not linked. Click the button again to reopen Telegram.");
      }
    }, POLL_INTERVAL_MS);
  }, [fetchTelegramStatus, stopPolling]);

  const startLinkFlow = useCallback(async () => {
    setErrorMessage("");

    const token = localStorage.getItem("access_token");
    if (!token) {
      stopPolling();
      setIsWaitingForLink(false);
      setErrorMessage("Not authenticated.");
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/notifications/telegram-link/start`, {
        method: "POST",
        headers: getAuthHeaders(),
      });

      if (!res.ok) {
        const message = await getResponseErrorMessage(res);
        throw new Error(message);
      }

      const data = await res.json();
      applyStatus(data);

      const linkInProgress = Boolean(data?.link_in_progress);
      if (!linkInProgress) {
        stopPolling();
        return;
      }

      const link = data?.telegram_link;
      if (!link) {
        setErrorMessage("Could not generate Telegram link. Please try again.");
        return;
      }

      const openedWindow = window.open(link, "_blank", "noopener,noreferrer");
      setIsWaitingForLink(true);
      if (!openedWindow) {
        setStatusMessage("Popup blocked. Use the manual bot link below to continue.");
      } else {
        setStatusMessage("Telegram opened. Tap Start in the bot and return here.");
      }
      startPollingForLink();
    } catch (err) {
      setErrorMessage(err?.message || "Failed to start Telegram link flow.");
    }
  }, [API_BASE, applyStatus, getResponseErrorMessage, startPollingForLink, stopPolling]);

  useEffect(() => {
    fetchTelegramStatus(true);
    return () => stopPolling();
  }, [fetchTelegramStatus, stopPolling]);

  useEffect(() => {
    if (isWaitingForLink) {
      startPollingForLink();
      return;
    }
    stopPolling();
  }, [isWaitingForLink, startPollingForLink, stopPolling]);

  useEffect(() => {
    if (!isWaitingForLink) {
      return undefined;
    }

    const handleFocus = () => {
      fetchTelegramStatus(false);
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        fetchTelegramStatus(false);
      }
    };

    window.addEventListener("focus", handleFocus);
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      window.removeEventListener("focus", handleFocus);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [fetchTelegramStatus, isWaitingForLink]);

  if (isLoading) {
    return <div className="card telegram-card">Loading notification settings...</div>;
  }

  const cardStateClass = isLinked ? "linked" : isWaitingForLink ? "waiting" : "unlinked";

  return (
    <div className="card telegram-card">
      <div className="telegram-header">
        <h2 className="card-title">Telegram Notifications</h2>
        <span className={`status-badge ${cardStateClass}`}>
          {isLinked ? "Connected" : isWaitingForLink ? "Waiting" : "Not Connected"}
        </span>
      </div>
      <p className="telegram-description">
        {isLinked 
          ? "You are currently receiving push notifications directly on your mobile device via Telegram." 
          : isWaitingForLink
            ? "Complete linking in Telegram by tapping Start, then return to this page."
            : "Connect your Telegram account to receive instant notifications about schedule updates and new constraints."}
      </p>

      {statusMessage && <p className="telegram-status-message">{statusMessage}</p>}
      {errorMessage && <p className="telegram-error-message">{errorMessage}</p>}
      
      {!isLinked && (
        <button 
          className="button telegram-btn" 
          onClick={startLinkFlow}
        >
          {isWaitingForLink ? "Open Telegram Again" : "Link to Telegram"}
        </button>
      )}

      {isLinked && (
        <button 
          className="button button-outline" 
          onClick={startLinkFlow}
        >
          Re-link in Telegram
        </button>
      )}

      {!isLinked && telegramLink && (
        <p className="telegram-fallback">
          If Telegram did not open, <a href={telegramLink} target="_blank" rel="noopener noreferrer">open the bot manually</a>.
        </p>
      )}
    </div>
  );
}

export default TelegramLinkingCard;
