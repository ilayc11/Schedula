// src/pages/ConstraintsWritePage.jsx
import { useEffect, useMemo, useRef, useState } from "react";
import "./ConstraintsWritePage.css";
import ParsedConstraintsMessage from "../../components/ParsedConstraintsMessage.jsx";
import StageProgressIndicator from "../../components/StageProgressIndicator.jsx";
import { useConstraintProgress } from "../../hooks/useConstraintProgress.js";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const LECTURER_PREFIX = import.meta.env.VITE_API_PREFIX_LECTURER || "/lecturer";
const API_BASE = API_BASE_URL + LECTURER_PREFIX;

function safeJsonParse(raw) {
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function getToken() {
  return localStorage.getItem("access_token");
}

function getUserData() {
  return safeJsonParse(localStorage.getItem("user_data") || "null");
}

// function formatRules(rules) {
//   if (!rules) return "";
//   if (typeof rules === "string") return rules;
//   try {
//     return JSON.stringify(rules, null, 2);
//   } catch {
//     return String(rules);
//   }
// }

function toNiceErrorText(err) {
  if (!err) return "Something went wrong.";

  // FastAPI validation errors (422) typically: { detail: [{loc,msg,type,...}, ...] }
  if (Array.isArray(err.detail)) {
    const lines = err.detail.map((e) => {
      const path = Array.isArray(e.loc) ? e.loc.join(".") : "field";
      const msg = e?.msg ? String(e.msg) : "Invalid value";
      return `${path}: ${msg}`;
    });
    return lines.join("\n");
  }

  if (typeof err.detail === "string") return err.detail;
  if (typeof err === "string") return err;

  try {
    return JSON.stringify(err, null, 2);
  } catch {
    return "Something went wrong.";
  }
}


function ConstraintsWritePage() {
  const [messages, setMessages] = useState(() => [
    {
      role: "bot",
      type: "text",
      text:
        "Write your constraints in free text.\n" +
        "I will parse them, show you a preview, then you can confirm and save.",
    },
  ]);

  const [input, setInput] = useState("");
  const [isBotTyping, setIsBotTyping] = useState(false);

  const [pendingPreview, setPendingPreview] = useState(null);
  const [lastRawText, setLastRawText] = useState("");

  const chatEndRef = useRef(null);
  const abortControllerRef = useRef(null);

  // WebSocket progress tracking
  const {
    currentStage,
    isConnected,
    isProcessing,
    startSession,
    endSession,
  } = useConstraintProgress();

  const hasPendingPreview = Boolean(pendingPreview);

  // const canSend = useMemo(() => input.trim().length > 0 && !isBotTyping, [input, isBotTyping]);
  // const canConfirmSave = useMemo(
  //   () => Boolean(pendingPreview) && !isBotTyping,
  //   [pendingPreview, isBotTyping]
  // );

  const canSend = useMemo(() => {
    const hasText = input.trim().length > 0;
    return hasText && !isBotTyping && !hasPendingPreview;}, [input, isBotTyping, hasPendingPreview]);

  function pushMessage(role, text) {
    setMessages((prev) => [...prev, { role, type: "text", text }]);
  }

  function pushPreview(structuredRules) {
    setMessages((prev) => [
      ...prev,
      {
        role: "bot",
        type: "preview",
        data: structuredRules,
        status: "pending",
      },
    ]);
  }

  function getCurrentSemesterFromStorage() {
    try {
      const raw = localStorage.getItem("current_semester");
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  }

  function markLastPreviewStatus(status) {
    // CHANGED: updates the last pending preview bubble so buttons get disabled immediately
    setMessages((prev) => {
      const copy = [...prev];
      for (let i = copy.length - 1; i >= 0; i--) {
        if (copy[i]?.type === "preview" && copy[i]?.status === "pending") {
          copy[i] = { ...copy[i], status };
          break;
        }
      }
      return copy;
    });
  }

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isBotTyping]);

  async function handleSend() {
    if (!canSend) return;

    const userText = input.trim();
    setInput("");
    setLastRawText(userText);
    pushMessage("user", userText);

    const token = getToken();
    const userData = getUserData();

    if (!token) {
      setPendingPreview(null);
      return;
    }

    setIsBotTyping(true);
    
    // Start WebSocket session for progress updates
    const sessionId = startSession();

    try {
      // const semester_year = 2025;
      // const semester_number = 1;
      const storedSemester = getCurrentSemesterFromStorage();
      const semester_year = storedSemester?.semester_year ?? userData?.current_semester_year ?? 2025;
      const semester_number = storedSemester?.semester_number ?? userData?.current_semester_number ?? 1;

      const controller = new AbortController();
      abortControllerRef.current = controller;

      // Include session_id as query parameter for WebSocket progress tracking
      const res = await fetch(`${API_BASE}/constraints/preview?session_id=${sessionId}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        signal: controller.signal,
        body: JSON.stringify({
          semester_year,
          semester_number,
          raw_text: userText,
        }),
      });

      const result = await res.json().catch(() => null);

      if (!res.ok) {
        pushMessage("bot", result?.detail || "Preview failed. Please try again.");
        setPendingPreview(null);
        return;
      }

      if (result?.status === "clarification_needed") {
        pushMessage("bot", result.message);
        setPendingPreview(null);
        return;
      }

      const constraintData = result?.data; 
      
      if (constraintData) {
        setPendingPreview(constraintData); 
        pushPreview(constraintData.structured_rules);   
      } else {
        pushMessage("bot", "Received successful response but no data was found.");
      }

    } catch (error) {
      // pushMessage("bot", "Network error while contacting the server.");
      if (error.name === "AbortError") {
        pushMessage("bot", "Chat refresh requested.");
      } else {
        pushMessage("bot", "Network error while contacting the server.");
      }
      setPendingPreview(null);
    } finally {
      setIsBotTyping(false);
      endSession(); // Clean up WebSocket session
    }
  }

  async function handleConfirmSave(editedStructuredRules) {
    if (!pendingPreview) return;

    const token = getToken();

    if (!token) {
      pushMessage("bot", "You are not logged in. Please login again.");
      return;
    }

    // Use the rules the lecturer edited in the preview if provided,
    // otherwise fall back to what the LLM originally returned.
    const structuredRulesToSave =
      editedStructuredRules && Array.isArray(editedStructuredRules.atomic_constraints)
        ? editedStructuredRules
        : pendingPreview.structured_rules;

    if (
      !structuredRulesToSave ||
      !Array.isArray(structuredRulesToSave.atomic_constraints) ||
      structuredRulesToSave.atomic_constraints.length === 0
    ) {
      pushMessage("bot", "There are no rules to save. Add at least one rule before saving.");
      return;
    }

    setIsBotTyping(true);
    pushMessage("bot", "Saving your constraints...");

    try {
      const res = await fetch(`${API_BASE}/constraints/save`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        // pendingPreview כבר מכיל את האובייקט הפנימי (מתוך ה-data של ה-preview)
        body: JSON.stringify({
          semester_year: pendingPreview.semester_year,
          semester_number: pendingPreview.semester_number,
          raw_text: pendingPreview.raw_text,
          structured_rules: structuredRulesToSave,
        }),
      });

      const result = await res.json().catch(() => null);

      if (!res.ok) {
        pushMessage("bot", toNiceErrorText(result) || "Save failed. Please try again.");
        return;
      }

      markLastPreviewStatus("approved");
      setPendingPreview(null);
      pushMessage("bot", "Saved. Do you want to add more constraints?");
    } catch (error) {
      pushMessage("bot", "Network error while saving.");
    } finally {
      setIsBotTyping(false);
    }
  }

  // function handleRejectPreview() {
  //   setPendingPreview(null);
  //   pushMessage("bot", "Understood, please rephrase the constraint and I will try again.");
  //   setInput("");
  // }
  
  function handleRejectPreview() {
    // CHANGED: close the preview bubble and continue the chat flow
    markLastPreviewStatus("rejected");
    setPendingPreview(null);
    pushMessage("bot", "Understood. Please rephrase the constraint and send again.");
    setInput("");
  }

  function handleRefreshChat() {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsBotTyping(false);
    endSession();
    pushMessage(
      "bot",
      "Conversation refreshed. You can continue normally."
    );
  }

  function handleKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (canSend)handleSend();
    }
  }

  return (
    <div className="content-container">
      <div className="page-header">
        <div>
          <h1 className="page-title">Write Constraints</h1>
          <p className="page-subtitle">
            Type your constraints naturally. You will get a preview, then confirm to save.
          </p>
        </div>
      </div>

      <div className="chat-card">
        <div className="chat-topbar">
          <div className="chat-badge">Schedula Assistant</div>
        </div>

        <div className="chat-list">
          {messages.map((m, idx) => (
            <div
              key={idx}
              className={`chat-row ${m.role === "user" ? "from-user" : "from-bot"}`}
            >
              <div className={`chat-bubble ${m.role === "user" ? "user" : "bot"}`}>
                {m.type === "preview" ? (
                  <ParsedConstraintsMessage
                    structuredRules={m.data}
                    // CHANGED: disable buttons when not pending, not only when pendingPreview exists
                    disabled={isBotTyping || m.status !== "pending"}
                    onApprove={handleConfirmSave}
                    onReject={handleRejectPreview}
                    approveText={m.status === "approved" ? "approved" : "approve"}
                    rejectText={m.status === "rejected" ? "rejected" : "reject"}
                  />
                  // <ParsedConstraintsMessage
                  //   structuredRules={m.data}
                  //   disabled={isBotTyping || !pendingPreview}
                  //   onApprove={handleConfirmSave}
                  //   onReject={handleRejectPreview}
                  // />
                ) : (
                  <p className="chat-line">{m.text}</p>
                )}
              </div>
            </div>
          ))}

          {isBotTyping && (
            <div className="chat-row from-bot">
              <div className="chat-bubble bot">
                <StageProgressIndicator
                  stageInfo={currentStage}
                  isConnecting={isProcessing && !isConnected}
                  fallback={!isProcessing || !currentStage}
                />
              </div>
            </div>
          )}

          <div ref={chatEndRef} />
        </div>

        <div className="chat-inputbar">
          <textarea
            className="chat-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            // placeholder="Write your constraints…"
            placeholder={hasPendingPreview ? "Please confirm or reject the preview above." : "Write your constraints…"}
            rows={2}
            disabled={isBotTyping}
          />

          <button className="chat-send" onClick={handleSend} disabled={!canSend} type="button">
            Send
          </button>
          <button className="chat-refresh" onClick={handleRefreshChat} type="button">
            ↻
          </button>

       </div>

        <div className="chat-hint">
          Tip: write multiple sentences, I will merge them into one constraint set.
        </div>
      </div>
    </div>
  );
}

export default ConstraintsWritePage;
