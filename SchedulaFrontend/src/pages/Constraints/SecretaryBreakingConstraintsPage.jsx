// src/pages/SecretaryBreakingConstraintsPage/SecretaryBreakingConstraintsPage.jsx
import { useEffect, useMemo, useState, useCallback, useRef } from "react";
import "./SecretaryBreakingConstraintsPage.css";

import DataTable from "../../components/DataTable.jsx";
import Tooltip from "../../components/Tooltip.jsx";
import YearPicker from "../../components/YearPicker.jsx";
import useCurrentSemester from "../../hooks/useCurrentSemester.js";
import { tooltipForType, tooltipForDay, tooltipForTime } from "../../components/tooltipTexts.js";
import { useMockMode } from "../../context/MockModeContext.jsx";
import ConfirmModal from "../../components/ConfirmModal.jsx";
import EditConstraintForm from "../../components/EditConstraintForm.jsx";
import EditIndicatorBadge from "../../components/EditIndicatorBadge.jsx";
import { Pencil, Trash2 } from "lucide-react";


const STATUS_OPTIONS = [
  { value: "Required", label: "Required" },
  { value: "Preferred", label: "Preferred" },
  // { value: "NULL", label: "NULL" },
];

const MOCK_SEMESTERS = [
  { id: "2025-1", label: "2025 / Semester A" },
  { id: "2025-2", label: "2025 / Semester B" },
];

const MOCK_LECTURERS = [
  { id: "all", label: "All lecturers" },
  { id: "101", label: "Dr. Cohen" },
  { id: "102", label: "Prof. Levi" },
];

const MOCK_BREAKING_CONSTRAINTS = [
  {
    id: "bc-1",
    breaking_id: 15,
    constraints_id: 42,
    semesterId: "2025-1",
    semester_year: 2025,
    semester_number: 1,
    lecturerId: "101",
    lecturer_internal_id: 101,
    lecturerName: "Dr. Cohen",
    title: "I prefer not to teach after 16:00",
    structured_rules: {
      atomic_constraints: [
        {
          atomic_constraint_index: 0,
          type: "block",
          days: [3],
          time_slot: { start_hour: 16, start_minute: 0, end_hour: 20, end_minute: 0 },
        },
        {
          atomic_constraint_index: 1,
          type: "block",
          days: [5],
          time_slot: { start_hour: 16, start_minute: 0, end_hour: 20, end_minute: 0 },
        },
      ],
    },
    status: "Preferred",
    created_at: "2026-01-20T10:00:00Z",
  },
  {
    id: "bc-2",
    breaking_id: 16,
    constraints_id: 55,
    semesterId: "2025-1",
    semester_year: 2025,
    semester_number: 1,
    lecturerId: null,
    lecturer_internal_id: null,
    lecturerName: null,
    title: "I can't teach on Friday",
    structured_rules: {
      atomic_constraints: [
        {
          atomic_constraint_index: 0,
          type: "block",
          days: [6],
          time_slot: null,
        },
      ],
    },
    status: "Required",
    created_at: "2026-01-20T10:00:00Z",
  },
];

const DAY_NAMES = {
  1: "SUNDAY",
  2: "MONDAY",
  3: "TUESDAY",
  4: "WEDNESDAY",
  5: "THURSDAY",
  6: "FRIDAY",
};

function pad2(n) {
  return String(n ?? 0).padStart(2, "0");
}

function lecturerInitials(name) {
  return String(name || "?")
    .replace(/^Dr\.?\s*/i, "")
    .split(" ")
    .filter(Boolean)
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function formatTimeSlot(ts) {
  if (!ts) return { from: "", to: "" };
  const from = `${pad2(ts.start_hour)}:${pad2(ts.start_minute ?? 0)}`;
  const to = `${pad2(ts.end_hour)}:${pad2(ts.end_minute ?? 0)}`;
  return { from, to };
}

function prettyRulesFromAtomicConstraints(atomicConstraints) {
  if (!Array.isArray(atomicConstraints)) return [];

  const rules = [];
  for (const a of atomicConstraints) {
    const type = String(a?.type || "RULE").toUpperCase();
    const days = Array.isArray(a?.days) ? a.days : [];
    const { from, to } = formatTimeSlot(a?.time_slot || null);

    if (days.length === 0) {
      rules.push({ type, day: "ANY_DAY", from, to });
      continue;
    }

    for (const d of days) {
      rules.push({ type, day: DAY_NAMES[d] || `DAY_${d}`, from, to });
    }
  }

  return rules;
}

function timeLabelForRule(r) {
  if (r.from && r.to) return `${r.from} - ${r.to}`;
  if (r.from) return `from ${r.from}`;
  if (r.to) return `until ${r.to}`;
  return "all day";
}

function SystemInterpretationCell({ row }) {
  const atomic = row?.structured_rules?.atomic_constraints ?? row?.breaking_atomic_constraints ?? [];
  const rules = prettyRulesFromAtomicConstraints(atomic);

  if (rules.length === 0) return <span className="no-rules">No structured rules parsed yet.</span>;

  return (
    <div className="constraint-rules-list">
      {rules.map((r, idx) => {
        const typeTip = tooltipForType(r.type);
        const dayTip = tooltipForDay(r.day);
        const timeTip = tooltipForTime(r.from, r.to);
        const timeLabel = timeLabelForRule(r);

        return (
          <div key={idx} className="constraint-rule-item">
            <span className="bullet" aria-hidden="true">
              •
            </span>

            <Tooltip text={typeTip}>
              <span className="cm-chip cm-chip-type">{r.type}</span>
            </Tooltip>

            <Tooltip text={dayTip}>
              <span className="cm-chip cm-chip-day">{r.day}</span>
            </Tooltip>

            <Tooltip text={timeTip}>
              <span className="cm-chip cm-chip-time">{timeLabel}</span>
            </Tooltip>
          </div>
        );
      })}
    </div>
  );
}

function semesterIdToYearNumber(semesterId) {
  const parts = String(semesterId ?? "").split("-");
  const year = Number(parts[0]);
  const number = Number(parts[1]);
  return { year, number };
}

function mapStatusToOverride(status) {
  if (status === "Required") return true;
  if (status === "Preferred") return false;
  return null;
}

function mapOverrideToStatus(value) {
  if (value === true) return "Required";
  if (value === false) return "Preferred";
  return "NULL";
}

/* ==============================
   REAL API HELPERS
============================== */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const SECRETARY_PREFIX = import.meta.env.VITE_API_PREFIX_SECRETARY || "/secretary";
const API_BASE = API_BASE_URL + SECRETARY_PREFIX;

function authHeaders() {
  const token = localStorage.getItem("access_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function fetchJson(url, options = {}) {
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(options.headers || {}),
    },
  });

  const isJson = res.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await res.json().catch(() => null) : null;

  if (!res.ok) {
    const detail = data?.detail;
    let message;
    if (detail && typeof detail === "object") {
      // Preserve structured detail (e.g. validation errors) as JSON so callers
      // can parse it back; falls through to a flat string otherwise.
      message = JSON.stringify(detail);
    } else {
      message = detail || data?.message || `Request failed (${res.status})`;
    }
    throw new Error(message);
  }

  if (res.status === 204) return null;
  return data;
}

async function apiListBreakingConstraints({ year, number, lecturerId }) {
  if (lecturerId && lecturerId !== "all") {
    return fetchJson(`${API_BASE}/breaking-constraints/lecturer/${lecturerId}/${year}/${number}`, { method: "GET" });
  }
  return fetchJson(`${API_BASE}/breaking-constraints/${year}/${number}`, { method: "GET" });
}

async function apiUpdateConstraintPriority({ constraintsId, nextStatus }) {
  return fetchJson(`${API_BASE}/manage-constraints/${constraintsId}/priority`, {
    method: "PATCH",
    body: JSON.stringify({ secretary_override_as_hard: mapStatusToOverride(nextStatus) }),
  });
}

async function apiDeleteConstraint(constraintsId) {
  return fetchJson(`${API_BASE}/manage-constraints/${constraintsId}`, {
    method: "DELETE",
  });
}

async function apiEditStructuredRules(constraintsId, payload) {
  return fetchJson(`${API_BASE}/manage-constraints/${constraintsId}/structured-rules`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

function normalizeBreakingResponse(payload) {
  const data = Array.isArray(payload) ? payload : payload?.data;
  const list = Array.isArray(data) ? data : [];

  return list.map((x) => {
    const breakingId = x.breaking_id ?? x.id;
    const constraintsId = x.constraints_id;

    return {
      id: String(breakingId ?? constraintsId ?? Math.random()),
      breaking_id: breakingId,
      constraints_id: constraintsId,
      breaking_atomic_constraints: x.breaking_atomic_constraints ?? [],
      structured_rules: x.structured_rules ?? null,
      semester_year: x.semester_year,
      semester_number: x.semester_number,
      lecturer_internal_id: x.lecturer_internal_id ?? null,
      lecturerName: x.lecturer_name ?? null,
      title: x.raw_text ?? x.constraint_text ?? (constraintsId ? `Constraint #${constraintsId}` : "Constraint"),
      raw_text: x.raw_text ?? null,
      is_manually_edited: Boolean(x.is_manually_edited),
      original_raw_text: x.original_raw_text ?? null,
      status: mapOverrideToStatus(x.secretary_override_as_hard),
      created_at: x.created_at,
    };
  });
}

function applyEditedConstraintToRow(row, updated) {
  if (!updated) return row;
  const nextStructured = updated.structured_rules ?? row.structured_rules;
  return {
    ...row,
    structured_rules: nextStructured,
    raw_text: updated.raw_text ?? row.raw_text,
    title: updated.raw_text ?? row.title,
    is_manually_edited: Boolean(updated.is_manually_edited ?? true),
    original_raw_text: updated.original_raw_text ?? row.original_raw_text,
  };
}

/* ==============================
   API LAYER: MOCK VS REAL
============================== */

function createMockApi() {
  let data = [...MOCK_BREAKING_CONSTRAINTS];

  return {
    list: async ({ semesterId, lecturerId }) => {
      const filtered = data.filter((r) => {
        if (semesterId && r.semesterId !== semesterId) return false;
        if (lecturerId !== "all" && String(r.lecturer_internal_id ?? r.lecturerId) !== String(lecturerId)) return false;
        return true;
      });
      return filtered;
    },

    updateStatus: async ({ rowId, nextStatus }) => {
      data = data.map((r) => (r.id === rowId ? { ...r, status: nextStatus } : r));
      return { ok: true };
    },

    delete: async ({ rowId }) => {
      data = data.filter((r) => r.id !== rowId);
      return { ok: true };
    },

    edit: async ({ rowId, payload }) => {
      let updated = null;
      data = data.map((r) => {
        if (r.id !== rowId) return r;
        const originalRaw = r.original_raw_text || r.title;
        const newTitle =
          payload.raw_text ||
          `Edited rules (${payload.structured_rules?.atomic_constraints?.length || 0} atomic)`;
        updated = {
          ...r,
          structured_rules: payload.structured_rules,
          raw_text: newTitle,
          title: newTitle,
          is_manually_edited: true,
          original_raw_text: originalRaw,
        };
        return updated;
      });
      return updated;
    },
  };
}

function createRealApi() {
  return {
    list: async ({ year, number, lecturerId }) => {
      const payload = await apiListBreakingConstraints({ year, number, lecturerId });
      return normalizeBreakingResponse(payload);
    },

    updateStatus: async ({ constraintsId, nextStatus }) => {
      await apiUpdateConstraintPriority({ constraintsId, nextStatus });
      return { ok: true };
    },
    
    delete: async ({ constraintsId }) => {
      await apiDeleteConstraint(constraintsId);
      return { ok: true };
    },

    edit: async ({ constraintsId, payload }) => {
      const res = await apiEditStructuredRules(constraintsId, payload);
      return res?.data ?? res;
    },
  };
}

function formatEditError(err) {
  if (!err) return "";
  // Backend 422 returns { status: "error", errors: [{path, message}, ...] } inside detail
  const message = err.message || "";
  try {
    const parsed = JSON.parse(message);
    if (Array.isArray(parsed?.errors)) {
      return parsed.errors.map((e) => `${e.path}: ${e.message}`).join("\n");
    }
  } catch {
    // fall through
  }
  return message || "Failed to save edit.";
}

/* ==============================
   PAGE
============================== */

export default function SecretaryBreakingConstraintsPage() {
  const { useMock } = useMockMode();

  const api = useMemo(() => (useMock ? createMockApi() : createRealApi()), [useMock]);

  // Filters
  const [semesterId, setSemesterId] = useState(MOCK_SEMESTERS[0]?.id ?? "");
  const [lecturerId, setLecturerId] = useState("all");

  // Real mode inputs (so you are not stuck with mock dropdowns)
  const initial = semesterIdToYearNumber(semesterId);
  const [realYear, setRealYear] = useState(initial.year || new Date().getFullYear());
  const [realNumber, setRealNumber] = useState(initial.number || 1);

  // Default the year filter to the current active semester's year (once).
  const { semesterYear } = useCurrentSemester({ enabled: !useMock });
  const appliedSemesterYearRef = useRef(false);
  useEffect(() => {
    if (!appliedSemesterYearRef.current && semesterYear) {
      setRealYear(semesterYear);
      appliedSemesterYearRef.current = true;
    }
  }, [semesterYear]);

  // Data
  const [rowsState, setRowsState] = useState([]);

  // UI states
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const [deleteTarget, setDeleteTarget] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const [editTarget, setEditTarget] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editError, setEditError] = useState("");

  const load = useCallback(async () => {
    setIsLoading(true);
    setError("");

    try {
      if (useMock) {
        const list = await api.list({ semesterId, lecturerId });
        setRowsState(Array.isArray(list) ? list : []);
        return;
      }

      if (!realYear || !realNumber) {
        setRowsState([]);
        return;
      }

      const list = await api.list({ year: Number(realYear), number: Number(realNumber), lecturerId });
      setRowsState(Array.isArray(list) ? list : []);
    } catch (e) {
      setRowsState([]);
      setError(e?.message || "Failed to load breaking constraints.");
    } finally {
      setIsLoading(false);
    }
  }, [api, useMock, semesterId, lecturerId, realYear, realNumber]);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      if (cancelled) return;
      await load();
    })();

    return () => {
      cancelled = true;
    };
  }, [load]);

  const handleChangeStatus = useCallback(
    async (row, nextStatus) => {
      setError("");

      const prev = rowsState;
      setRowsState((curr) => curr.map((r) => (r.id === row.id ? { ...r, status: nextStatus } : r)));

      try {
        if (useMock) {
          await api.updateStatus({ rowId: row.id, nextStatus });
          return;
        }

        await api.updateStatus({
          constraintsId: row.constraints_id,
          nextStatus,
        });
      } catch (e) {
        setRowsState(prev);
        setError(e?.message || "Failed to update status.");
      }
    },
    [api, useMock, rowsState]
  );

    const handleDelete = useCallback(
    async (row) => {
      setError("");

      const prev = rowsState;
      setRowsState((curr) => curr.filter((r) => r.id !== row.id));

      try {
        if (useMock) {
          await api.delete({ rowId: row.id });
          return;
        }

        await api.delete({ constraintsId: row.constraints_id });
      } catch (e) {
        setRowsState(prev);
        setError(e?.message || "Failed to delete constraint.");
      }
    },
    [api, useMock, rowsState]
  );

  const handleDeleteConfirmed = useCallback(async () => {
    if (!deleteTarget) return;

    setError("");
    setIsDeleting(true);

    try {
        await handleDelete(deleteTarget);
        setDeleteTarget(null);
    } finally {
        setIsDeleting(false);
    }
    }, [deleteTarget, handleDelete]);

  const handleEditSave = useCallback(
    async (payload) => {
      if (!editTarget) return;
      setEditError("");
      setIsEditing(true);

      try {
        const updated = useMock
          ? await api.edit({ rowId: editTarget.id, payload })
          : await api.edit({ constraintsId: editTarget.constraints_id, payload });

        setRowsState((curr) =>
          curr.map((r) => (r.id === editTarget.id ? applyEditedConstraintToRow(r, updated) : r))
        );
        setEditTarget(null);
      } catch (e) {
        setEditError(formatEditError(e) || "Failed to save edit.");
      } finally {
        setIsEditing(false);
      }
    },
    [api, useMock, editTarget]
  );

  const handleEditCancel = useCallback(() => {
    if (isEditing) return;
    setEditTarget(null);
    setEditError("");
  }, [isEditing]);


  const columns = useMemo(
    () => [

      {
        header: "Lecturer",
        render: (row) => {
          const label =
            row.lecturerName ||
            (row.lecturer_internal_id != null ? `ID ${row.lecturer_internal_id}` : null);
          if (!label) return <span className="bc-muted">-</span>;
          return (
            <div className="bc-lecturer-cell">
              <div className="bc-lecturer-avatar">{lecturerInitials(label)}</div>
              <span className="bc-lecturer-name">{label}</span>
            </div>
          );
        },
      },
      {
        header: "Constraint",
        key: "title",
        render: (row) => (
          <div className="bc-constraint-cell">
            <span className="bc-constraint-text">{row.title}</span>
            <EditIndicatorBadge
              isEdited={Boolean(row.is_manually_edited)}
              originalRawText={row.original_raw_text}
              className="bc-edit-badge"
            />
          </div>
        ),
      },
      {
        header: "System Interpretation",
        render: (row) => (
          <div className="bc-system-cell">
            <SystemInterpretationCell row={row} />
          </div>
        ),
      },
      {
        header: "Status",
        render: (row) => (
          <select
            className={`bc-status-select ${
              row.status === "Required" ? "bc-status-required" : "bc-status-preferred"}`}
            value={row.status}
            onClick={(e) => e.stopPropagation()}
            onChange={(e) => {
              e.stopPropagation();
              handleChangeStatus(row, e.target.value);
            }}
            disabled={isLoading}
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        ),
      },
      {
        header: "Actions",
        render: (row) => (
          <div className="bc-actions-cell">
                        <button
              type="button"
              className="ac-action-btn ac-action-edit"
              onClick={(e) => {
                e.stopPropagation();
                setEditError("");
                setEditTarget(row);
              }}
              disabled={isLoading || isDeleting || isEditing}
            >
              <Pencil size={15} strokeWidth={2.2} />
              <span>Edit</span>
            </button>

            <button
              type="button"
              className="ac-action-btn ac-action-delete"
              onClick={(e) => {
                e.stopPropagation();
                setDeleteTarget(row);
              }}
              disabled={isLoading || isDeleting || isEditing}
            >
              <Trash2 size={15} strokeWidth={2.2} />
              <span>Delete</span>
            </button>
          </div>
        ),
      },
    ],
    [isLoading, isDeleting, isEditing, handleChangeStatus]
  );

  return (
    <section className="main-content">
      <div className="bc-head">
        <div>
          <h1 className="bc-h1">Breaking Constraints</h1>
          <div className="bc-sub">Review the system interpretation, then set each constraint to Required or Preferred.</div>
        </div>

        <div className="bc-filters">
          {useMock ? (
            <>
              <label className="bc-filter">
                <span className="bc-label">Semester</span>
                <select
                  className="bc-select"
                  value={semesterId}
                  onChange={(e) => {
                    const next = e.target.value;
                    setSemesterId(next);
                    const yn = semesterIdToYearNumber(next);
                    setRealYear(yn.year || new Date().getFullYear());
                    setRealNumber(yn.number || 1);
                  }}
                  disabled={isLoading}
                >
                  {MOCK_SEMESTERS.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </label>

              <label className="bc-filter">
                <span className="bc-label">Lecturer</span>
                <select
                  className="bc-select"
                  value={lecturerId}
                  onChange={(e) => setLecturerId(e.target.value)}
                  disabled={isLoading}
                >
                  {MOCK_LECTURERS.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.label}
                    </option>
                  ))}
                </select>
              </label>
            </>
          ) : (
            <>
              <label className="bc-filter">
                <span className="bc-label">Year</span>
                <YearPicker
                  year={realYear}
                  onChange={setRealYear}
                  disabled={isLoading}
                  className="bc-select"
                />
              </label>

              <label className="bc-filter">
                <span className="bc-label">Semester</span>
                <input
                  className="bc-select"
                  type="number"
                  value={realNumber}
                  onChange={(e) => setRealNumber(e.target.value)}
                  disabled={isLoading}
                />
              </label>

              <label className="bc-filter">
                <span className="bc-label">Lecturer</span>
                <input
                  className="bc-select"
                  value={lecturerId}
                  onChange={(e) => setLecturerId(e.target.value || "all")}
                  disabled={isLoading}
                  placeholder='Type lecturer id or "all"'
                />
              </label>
            </>
          )}
        </div>
      </div>

      {error ? <div className="bc-error">{error}</div> : null}

      <DataTable
        columns={columns}
        rows={rowsState}
        rowKey={(r) => r.id}
        emptyText={isLoading ? "Loading..." : "No breaking constraints found for the selected filters."}
        // wrapClassName="assignments-table-wrap"
        // tableClassName="assignments-table"
        wrapClassName="bc-table-wrap"
        tableClassName="bc-table"
      />
      <ConfirmModal
        open={Boolean(deleteTarget)}
        title="Delete constraint?"
        message={
            deleteTarget
            ? `You're about to delete this constraint. This action cannot be undone.`
            : ""
        }
        confirmText="Delete"
        cancelText="Cancel"
        onCancel={() => setDeleteTarget(null)}
        onConfirm={handleDeleteConfirmed}
        loading={isDeleting}
        />

      <EditConstraintForm
        open={Boolean(editTarget)}
        constraint={editTarget}
        onCancel={handleEditCancel}
        onSave={handleEditSave}
        loading={isEditing}
        error={editError}
      />
    </section>
  );
}
