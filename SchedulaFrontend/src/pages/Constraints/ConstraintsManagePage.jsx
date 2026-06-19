import { useEffect, useMemo, useState } from "react";
import "./ConstraintsManagePage.css";
import ParsedConstraintsMessage from "../../components/ParsedConstraintsMessage";
import { useMockMode } from "../../context/MockModeContext.jsx";
import Tooltip from "../../components/Tooltip.jsx";
import { tooltipForType, tooltipForDay, tooltipForTime } from "../../components/tooltipTexts.js";
import ConfirmModal from "../../components/ConfirmModal.jsx";
import EditIndicatorBadge from "../../components/EditIndicatorBadge.jsx";


const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const LECTURER_PREFIX = import.meta.env.VITE_API_PREFIX_LECTURER || "/lecturer";
const API_BASE = API_BASE_URL + LECTURER_PREFIX;

const API_PREFIX = "/constraints";

// Mock data for multiple constraints
const MOCK_CONSTRAINTS = [
  {
    constraints_id: 42,
    lecturer_internal_id: 101,
    semester_year: 2026,
    semester_number: 1,
    raw_text: "I need to leave by 4 PM on Tuesdays and Thursdays for my own class.",
    structured_rules: {
      atomic_constraints: [
        { type: "block", days: [3], time_slot: { start_hour: 16, start_minute: 0, end_hour: 20, end_minute: 0 } },
        { type: "block", days: [5], time_slot: { start_hour: 16, start_minute: 0, end_hour: 20, end_minute: 0 } },
      ]
    },
    last_updated_at: "2025-12-07T12:05:00",
  },
  {
    constraints_id: 41,
    lecturer_internal_id: 101,
    semester_year: 2026,
    semester_number: 1,
    raw_text: "I cannot teach on Mondays before 10 AM.",
    structured_rules: {
      atomic_constraints: [
        { type: "block", days: [2], time_slot: { start_hour: 8, start_minute: 0, end_hour: 10, end_minute: 0 } },
      ]
    },
    last_updated_at: "2025-12-05T09:30:00",
  },
];

function getAccessToken() {
  return localStorage.getItem("access_token") || "";
}

function getUserData() {
  try {
    return JSON.parse(localStorage.getItem("user_data") || "null") || {};
  } catch {
    return {};
  }
}

function resolveLecturerInternalId() {
  const ud = getUserData();
  return ud?.lecturer_id ?? ud?.lecturer_internal_id ?? ud?.id ?? null;
}

function formatSemester(semester_year, semester_number) {
  const map = { 1: "Fall", 2: "Spring", 3: "Summer" };
  const label = map[semester_number] || "Semester";
  return `${label} ${semester_year}`;
}

function formatDate(dateStr) {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

// Day mapping for display (1-indexed: 1=Sunday, 6=Friday)
const DAY_NAMES = {
  1: "SUNDAY",
  2: "MONDAY",
  3: "TUESDAY",
  4: "WEDNESDAY",
  5: "THURSDAY",
  6: "FRIDAY",
};

function formatTimeSlot(ts) {
  if (!ts) return "All day";
  const sh = String(ts.start_hour || 0).padStart(2, "0");
  const sm = String(ts.start_minute || 0).padStart(2, "0");
  const eh = String(ts.end_hour || 0).padStart(2, "0");
  const em = String(ts.end_minute || 0).padStart(2, "0");
  return `${sh}:${sm} - ${eh}:${em}`;
}

function prettyRulesFromStructured(structured_rules) {
  if (!structured_rules) return [];

  const atomics = structured_rules.atomic_constraints || structured_rules;
  if (!Array.isArray(atomics)) return [];

  const rules = [];

  for (const r of atomics) {
    const type = String(r?.type || "RULE").toUpperCase();
    const days = Array.isArray(r?.days) ? r.days : [];
    const slot = r?.time_slot || null;

    const from = slot ? `${String(slot.start_hour ?? 0).padStart(2, "0")}:${String(slot.start_minute ?? 0).padStart(2, "0")}` : "";
    const to = slot ? `${String(slot.end_hour ?? 0).padStart(2, "0")}:${String(slot.end_minute ?? 0).padStart(2, "0")}` : "";

    if (days.length === 0) {
      rules.push({ type, day: "ANY_DAY", from, to });
      continue;
    }

    for (const dayIdx of days) {
      rules.push({ type, day: DAY_NAMES[dayIdx] || `DAY_${dayIdx}`, from, to });
    }
  }
  return rules;
}

/* ==============================
   REAL API HELPERS
============================== */
function unwrapApiResponse(res) {
// backend returns { status, data } in success cases
  if (res && typeof res === "object" && "data" in res) return res.data;
  return res;
}

function getApiStatus(res) {
  if (res && typeof res === "object" && "status" in res) return res.status;
  return "success";
}
async function apiFetch(path, options = {}) {
  const token = getAccessToken();

  const res = await fetch(`${API_BASE}${API_PREFIX}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  const isJson = res.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await res.json().catch(() => null) : null;

  if (!res.ok) {
    const message = data?.detail || data?.message || `Request failed (${res.status})`;
    throw new Error(message);
  }

  return data;
}

/* ==============================
   API LAYER: MOCK VS REAL
============================== */
function createMockApi() {
  let mockData = [...MOCK_CONSTRAINTS];

  return {
    myConstraints: async () => mockData,
    latest: async () => mockData[0] || null,

    previewCreate: async (payload) => ({
      constraints_id: null,
      lecturer_internal_id: 101,
      raw_text: payload.raw_text,
      semester_year: payload.semester_year,
      semester_number: payload.semester_number,
      structured_rules: {
        atomic_constraints: [
          { type: "block", days: [2], time_slot: null }
        ]
      },
      last_updated_at: new Date().toISOString(),
    }),

    previewEdit: async (constraintId, payload) => ({
      constraints_id: constraintId,
      lecturer_internal_id: 101,
      raw_text: payload.raw_text,
      semester_year: payload.semester_year,
      semester_number: payload.semester_number,
      structured_rules: {
        atomic_constraints: [
          { type: "block", days: [2], time_slot: null }
        ]
      },
      last_updated_at: new Date().toISOString(),
    }),

    save: async (payload) => {
      const saved = {
        ...payload,
        constraints_id: payload.constraints_id || Date.now(),
        last_updated_at: new Date().toISOString(),
      };
      // Update mock data
      const idx = mockData.findIndex(c => c.constraints_id === saved.constraints_id);
      if (idx >= 0) {
        mockData[idx] = saved;
      } else {
        mockData.unshift(saved);
      }
      return saved;
    },

    delete: async (constraintId) => {
      mockData = mockData.filter(c => c.constraints_id !== constraintId);
      return { success: true };
    },
  };
}


function createRealApi() {
  return {
    myConstraints: async () => unwrapApiResponse(await apiFetch("/my_constraints", { method: "GET" })),
    latest: async () => unwrapApiResponse(await apiFetch("/latest", { method: "GET" })),

    previewCreate: async (payload) =>
      unwrapApiResponse(await apiFetch("/preview", {
        method: "POST",
        body: JSON.stringify(payload),
        headers: {
          "X-Constraint-Operation": "create"
        }
      })),

    // Use X-Constraint-Operation header to indicate edit mode
    previewEdit: async (_constraintId, payload) =>
      unwrapApiResponse(await apiFetch("/preview", {
        method: "POST",
        body: JSON.stringify(payload),
        headers: {
          "X-Constraint-Operation": "edit"
        }
      })),

    save: async (payload) =>
      unwrapApiResponse(await apiFetch("/save", {
        method: "POST",
        body: JSON.stringify(payload),
      })),

    delete: async (constraintId) =>
      unwrapApiResponse(await apiFetch(`/${constraintId}`, {
        method: "DELETE",
      })),
  };
}


function inferTypeFromPrettyLine(line) {
  const s = String(line || "").toUpperCase();
  if (s.includes("BLOCK")) return "BLOCK";
  if (s.includes("PREFERENCE")) return "PREFERENCE";
  return "";
}


function ConstraintsManagePage() {
  // Use global mock mode from context
  const { useMock } = useMockMode();

  // Dynamic API based on toggle
  const api = useMemo(() => useMock ? createMockApi() : createRealApi(), [useMock]);

  // All constraints for the lecturer
  const [constraints, setConstraints] = useState([]);

  // Editing state
  const [isEditing, setIsEditing] = useState(false);
  const [editingConstraint, setEditingConstraint] = useState(null);
  const [draft, setDraft] = useState("");
  const [preview, setPreview] = useState(null);

  // UI states
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const [deleteTarget, setDeleteTarget] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);


  // Load all constraints
  async function loadConstraints() {
    setError("");
    setIsLoading(true);

    try {
      const data = await api.myConstraints();
      setConstraints(Array.isArray(data) ? data : []);
      setPreview(null);
      setIsEditing(false);
      setEditingConstraint(null);
    } catch (e) {
      setConstraints([]);
      setError(e.message || "Failed to load constraints");
    } finally {
      setIsLoading(false);
    }
  }

  // Re-fetch when toggle changes
  useEffect(() => {
    loadConstraints();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [useMock]);

  function startEdit(constraint) {
    setError("");
    setPreview(null);
    setEditingConstraint(constraint);
    setDraft(constraint.raw_text || "");
    setIsEditing(true);
  }

  function cancelEdit() {
    setError("");
    setPreview(null);
    setEditingConstraint(null);
    setDraft("");
    setIsEditing(false);
  }

  async function handlePreview() {
    setError("");

    const cleanText = draft.trim();
    if (!cleanText) {
      setError("Please enter constraints text");
      return;
    }

    const semester_year = editingConstraint?.semester_year || 2026;
    const semester_number = editingConstraint?.semester_number || 1;
    // const lecturer_id = resolveLecturerInternalId();
    const lecturer_id = editingConstraint?.lecturer_internal_id ?? resolveLecturerInternalId();


    if (!useMock && !lecturer_id) {
      setError("Missing lecturer internal id, check what you store in user_data after login");
      return;
    }

    const payload = { raw_text: cleanText, semester_year, semester_number, lecturer_id };

    setIsPreviewing(true);

    try {
      const constraintId = editingConstraint?.constraints_id;

      // data here is already unwrapped (the inner object) because createRealApi unwraps
      const data = constraintId
        ? await api.previewEdit(constraintId, payload)
        : await api.previewCreate(payload);

      setPreview(data);
    } catch (e) {
      setPreview(null);
      setError(e.message || "Preview failed");
    } finally {
      setIsPreviewing(false);
    }

  }

  async function handleSave() {
    setError("");

    if (!preview) {
      setError("Please run Preview first");
      return;
    }

    const lecturer_internal_id = preview.lecturer_internal_id ?? resolveLecturerInternalId();

    if (!useMock && !lecturer_internal_id) {
      setError("Missing lecturer internal id, check what you store in user_data after login");
      return;
    }

    const savePayload = {
      constraints_id: editingConstraint?.constraints_id ?? undefined,
      lecturer_internal_id,
      semester_year: preview.semester_year,
      semester_number: preview.semester_number,
      raw_text: preview.raw_text,
      structured_rules: preview.structured_rules,
      
    };

    setIsSaving(true);

    try {
      await api.save(savePayload);
      // Reload all constraints
      await loadConstraints();
    } catch (e) {
      setError(e.message || "Save failed");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDeleteConfirmed() {
    const constraintId = deleteTarget?.constraints_id;
    if (!constraintId) return;

    setError("");
    setIsDeleting(true);

    try {
      await api.delete(constraintId);
      setConstraints((prev) => prev.filter((c) => c.constraints_id !== constraintId));
      setDeleteTarget(null);
    } catch (e) {
      setError(String(e?.message || e || "Failed to delete constraint"));
    } finally {
      setIsDeleting(false);
    }
  }

  async function handleDelete(constraintId) {
    if (!window.confirm("Are you sure you want to delete this constraint? This action cannot be undone.")) {
      return;
    }

    setError("");
    setIsLoading(true);

    try {
      await api.delete(constraintId);
      // Remove from local state
      setConstraints(prev => prev.filter(c => c.constraints_id !== constraintId));
    } catch (e) {
      setError(String(e?.message || e || "Failed to delete constraint"));
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="content-container">
      <div className="summary-header">
        <div>
          <h1 className="summary-title">My Submitted Constraints</h1>
          <p className="summary-subtitle">
            {isLoading ? "Loading your constraints..." : `${constraints.length} constraint(s) found`}
          </p>
        </div>

        <div className="summary-actions">
          {!isEditing && (
            <button className="btn-ghost" onClick={loadConstraints} disabled={isLoading}>
              Refresh
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="panel cm-panel-error">
          <div className="panel-head">ERROR</div>
          <div className="panel-body-list">{error}</div>
        </div>
      )}

      {/* Loading State */}
      {isLoading && (
        <div className="constraints-loading">
          <div className="spinner" />
          <span>Loading constraints...</span>
        </div>
      )}

      {/* Empty State */}
      {!isLoading && constraints.length === 0 && (
        <div className="panel">
          <div className="panel-head">NO CONSTRAINTS</div>
          <div className="panel-body-list">
            <span>No constraints submitted yet. Go to the Write page to add your first constraint.</span>
          </div>
        </div>
      )}

      {/* Editing Panel */}
      {isEditing && editingConstraint && (
        <section className="panel cm-panel-editing">
          <div className="panel-head">
            EDITING CONSTRAINT #{editingConstraint.constraints_id}
          </div>
          <div className="panel-body-list">
            <textarea
              className="panel-editor"
              style={{ minHeight: 100 }}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              placeholder="Enter your constraint text..."
            />
            <div className="edit-actions" style={{ marginTop: 10 }}>
              <button className="btn-ghost" onClick={cancelEdit} disabled={isPreviewing || isSaving}>
                Cancel
              </button>
              <button className="btn-primary" onClick={handlePreview} disabled={isPreviewing || isSaving}>
                {isPreviewing ? "Previewing..." : "Preview"}
              </button>
            </div>
          </div>

          {preview && (
            <div className="panel-body-list" style={{ borderTop: "1px solid var(--color-border-subtle)" }}>
              <div style={{ fontWeight: 700, marginBottom: 8 }}>PREVIEW - System Interpretation:</div>
              <ParsedConstraintsMessage
                structuredRules={preview.structured_rules}
                disabled={isPreviewing || isSaving}
                title="This is how I understood your constraint"
                approveText="Approve & Save"
                rejectText="Reject"
                onApprove={handleSave}
                onReject={() => setPreview(null)}
              />
            </div>
          )}
        </section>
      )}

      {/* All Constraints - Connected View */}
      {!isLoading && !isEditing && constraints.map((constraint) => (
        <section key={constraint.constraints_id} className="constraint-card panel">
          <div className="constraint-card-header">
            <div className="constraint-card-meta">
              <span className="constraint-id">Constraint #{constraint.constraints_id}</span>
              <span className="constraint-semester">
                {formatSemester(constraint.semester_year, constraint.semester_number)}
              </span>
              {constraint.last_updated_at && (
                <span className="constraint-date">
                  Updated: {formatDate(constraint.last_updated_at)}
                </span>
              )}
              <EditIndicatorBadge
                isEdited={Boolean(constraint.is_manually_edited)}
                originalRawText={constraint.original_raw_text}
              />
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <button
                className="btn-ghost cm-btn cm-btn-edit"
                onClick={() => startEdit(constraint)}
              >
                Edit
              </button>

              <button
                className="btn-ghost cm-btn cm-btn-delete"
                onClick={() => setDeleteTarget(constraint)}
                disabled={isLoading || isDeleting}
              >
                Delete
              </button>
            </div>
          </div>

          <div className="constraint-card-section">
            <div className="constraint-section-title">
              {constraint.is_manually_edited ? "CURRENT TEXT (after secretary edit)" : "ORIGINAL TEXT"}
            </div>
            <div className="constraint-raw-text">
              "{constraint.raw_text}"
            </div>
            {constraint.is_manually_edited && constraint.original_raw_text ? (
              <div className="constraint-original-text-block">
                <div className="constraint-section-title constraint-original-title">
                  YOUR ORIGINAL TEXT
                </div>
                <div className="constraint-raw-text constraint-original-text">
                  "{constraint.original_raw_text}"
                </div>
              </div>
            ) : null}
          </div>

          <div className="constraint-card-section constraint-rules-section">
            <div className="constraint-section-title">ACTIVE RULES (System Interpretation)</div>
            <div className="constraint-rules-list">
              {prettyRulesFromStructured(constraint.structured_rules).length === 0 ? (
                <span className="no-rules">No structured rules parsed yet.</span>
              ) : (
                prettyRulesFromStructured(constraint.structured_rules).map((r, idx) => {
                  const typeTip = tooltipForType(r.type);

                  const dayTip =
                    r.day === "ANY_DAY"
                      ? "No specific day here, this rule may apply more generally."
                      : `This rule applies on ${r.day}.`;

                  const timeTip =
                    r.from && r.to
                      ? `Time window: ${r.from} to ${r.to}. The scheduler will avoid placing a class inside this window.`
                      : r.from
                        ? `From ${r.from} and onward. The scheduler will avoid placing a class starting at this time.`
                        : r.to
                          ? `Until ${r.to}. The scheduler will avoid placing a class before this time.`
                          : "All day. No specific hours were provided for this rule.";

                  const timeLabel =
                    r.from && r.to ? `${r.from} - ${r.to}` : r.from ? `from ${r.from}` : r.to ? `until ${r.to}` : "all day";

                  return (
                    <div key={idx} className="constraint-rule-item">
                      <span className="bullet">•</span>

                      <Tooltip text={typeTip}>
                        <span className="cm-chip cm-chip-type">{r.type}</span>
                      </Tooltip>

                      <span className="cm-divider">|</span>

                      <Tooltip text={dayTip}>
                        <span className="cm-chip cm-chip-day">{r.day}</span>
                      </Tooltip>

                      <span className="cm-divider">|</span>

                      <Tooltip text={timeTip}>
                        <span className="cm-chip cm-chip-time">{timeLabel}</span>
                      </Tooltip>
                    </div>
                  );
                })
              )}

            </div>
          </div>
        </section>
      ))}
      <ConfirmModal
        open={Boolean(deleteTarget)}
        title="Delete constraint?"
        message={
          deleteTarget
            ? `You're about to delete constraint #${deleteTarget.constraints_id}. This action cannot be undone.`
            : ""
        }
        confirmText="Delete"
        cancelText="Cancel"
        onCancel={() => setDeleteTarget(null)}
        onConfirm={handleDeleteConfirmed}
        loading={isDeleting}
      />

    </div>
  );
}

export default ConstraintsManagePage;
