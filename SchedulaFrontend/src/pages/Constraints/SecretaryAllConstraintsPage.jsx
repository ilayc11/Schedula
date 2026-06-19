// src/pages/Constraints/SecretaryAllConstraintsPage.jsx
//
// Secretary-facing page that lists ALL lecturer constraints (not just breaking
// ones), with full edit parity with SecretaryBreakingConstraintsPage. The
// "Show only breaking" toggle filters down to the breaking subset.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "./SecretaryAllConstraintsPage.css";

import DataTable from "../../components/DataTable.jsx";
import Tooltip from "../../components/Tooltip.jsx";
import YearPicker from "../../components/YearPicker.jsx";
import useCurrentSemester from "../../hooks/useCurrentSemester.js";
import {
  tooltipForType,
  tooltipForDay,
  tooltipForTime,
} from "../../components/tooltipTexts.js";
import { useMockMode } from "../../context/MockModeContext.jsx";
import ConfirmModal from "../../components/ConfirmModal.jsx";
import EditConstraintForm from "../../components/EditConstraintForm.jsx";
import EditIndicatorBadge from "../../components/EditIndicatorBadge.jsx";
import { Pencil, Trash2 } from "lucide-react";

const STATUS_OPTIONS = [
  { value: "HARD", label: "Required" },
  { value: "SOFT", label: "Preferred" },
];

const DAY_NAMES = {
  1: "SUNDAY",
  2: "MONDAY",
  3: "TUESDAY",
  4: "WEDNESDAY",
  5: "THURSDAY",
  6: "FRIDAY",
};

const MOCK_LECTURERS = [
  { id: "all", label: "All lecturers" },
  { id: "101", label: "Dr. Cohen" },
  { id: "102", label: "Prof. Levi" },
];

const MOCK_ALL_CONSTRAINTS = [
  {
    id: "ac-1",
    constraints_id: 42,
    semester_year: 2025,
    semester_number: 1,
    lecturer_internal_id: 101,
    lecturerName: "Dr. Cohen",
    title: "I prefer not to teach after 16:00",
    raw_text: "I prefer not to teach after 16:00",
    structured_rules: {
      atomic_constraints: [
        {
          type: "block",
          days: [3],
          time_slot: { start_hour: 16, start_minute: 0, end_hour: 20, end_minute: 0 },
          priority: "soft",
        },
        {
          type: "block",
          days: [5],
          time_slot: { start_hour: 16, start_minute: 0, end_hour: 20, end_minute: 0 },
          priority: "soft",
        },
      ],
    },
    is_manually_edited: false,
    original_raw_text: null,
    is_breaking: true,
    status: "SOFT",
  },
  {
    id: "ac-2",
    constraints_id: 51,
    semester_year: 2025,
    semester_number: 1,
    lecturer_internal_id: 102,
    lecturerName: "Prof. Levi",
    title: "Prefer mornings",
    raw_text: "Prefer mornings",
    structured_rules: {
      atomic_constraints: [
        {
          type: "preference",
          days: [1, 2, 3, 4, 5],
          time_slot: { start_hour: 8, start_minute: 0, end_hour: 12, end_minute: 0 },
          priority: "soft",
        },
      ],
    },
    is_manually_edited: false,
    original_raw_text: null,
    is_breaking: false,
    status: "NULL",
  },
  {
    id: "ac-3",
    constraints_id: 55,
    semester_year: 2025,
    semester_number: 1,
    lecturer_internal_id: 101,
    lecturerName: "Dr. Cohen",
    title: "Manually adjusted by secretary",
    raw_text: "Blocks Friday all day (hard)",
    structured_rules: {
      atomic_constraints: [
        {
          type: "block",
          days: [6],
          time_slot: null,
          priority: "hard",
        },
      ],
    },
    is_manually_edited: true,
    original_raw_text: "I cannot teach on Fridays at all.",
    is_breaking: true,
    status: "HARD",
  },
];

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
  const atomic = row?.structured_rules?.atomic_constraints ?? [];
  const rules = prettyRulesFromAtomicConstraints(atomic);

  if (rules.length === 0) {
    return <span className="no-rules">No structured rules parsed yet.</span>;
  }

  return (
    <div className="constraint-rules-list">
      {rules.map((r, idx) => {
        const typeTip = tooltipForType(r.type);
        const dayTip = tooltipForDay(r.day);
        const timeTip = tooltipForTime(r.from, r.to);
        const timeLabel = timeLabelForRule(r);

        return (
          <div key={idx} className="constraint-rule-item">
            <span className="bullet" aria-hidden="true">•</span>
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

function mapStatusToOverride(status) {
  if (status === "HARD") return true;
  if (status === "SOFT") return false;
  return null;
}

function mapOverrideToStatus(value) {
  if (value === true) return "HARD";
  if (value === false) return "SOFT";
  return "NULL";
}

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const SECRETARY_PREFIX =
  import.meta.env.VITE_API_PREFIX_SECRETARY || "/secretary";
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
      message = JSON.stringify(detail);
    } else {
      message = detail || data?.message || `Request failed (${res.status})`;
    }
    throw new Error(message);
  }

  if (res.status === 204) return null;
  return data;
}

function formatEditError(err) {
  if (!err) return "";
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

async function apiSearchConstraints({ year, number, lecturerId }) {
  const params = new URLSearchParams();
  if (year) params.set("semester_year", String(year));
  if (number) params.set("semester_number", String(number));
  if (lecturerId && lecturerId !== "all") {
    params.set("lecturer_id", String(lecturerId));
  }
  const url = `${API_BASE}/manage-constraints/search?${params.toString()}`;
  return fetchJson(url, { method: "GET" });
}

async function apiListBreakingForSemester({ year, number }) {
  return fetchJson(`${API_BASE}/breaking-constraints/${year}/${number}`, {
    method: "GET",
  });
}

async function apiUpdateConstraintPriority({ constraintsId, nextStatus }) {
  return fetchJson(
    `${API_BASE}/manage-constraints/${constraintsId}/priority`,
    {
      method: "PATCH",
      body: JSON.stringify({
        secretary_override_as_hard: mapStatusToOverride(nextStatus),
      }),
    }
  );
}

async function apiDeleteConstraint(constraintsId) {
  return fetchJson(`${API_BASE}/manage-constraints/${constraintsId}`, {
    method: "DELETE",
  });
}

async function apiEditStructuredRules(constraintsId, payload) {
  return fetchJson(
    `${API_BASE}/manage-constraints/${constraintsId}/structured-rules`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
    }
  );
}

function normalizeAllResponse(payload, breakingIds) {
  const data = Array.isArray(payload) ? payload : payload?.data;
  const list = Array.isArray(data) ? data : [];

  return list.map((x) => {
    const constraintsId = x.constraints_id;
    return {
      id: String(constraintsId ?? Math.random()),
      constraints_id: constraintsId,
      semester_year: x.semester_year,
      semester_number: x.semester_number,
      lecturer_internal_id: x.lecturer_internal_id ?? null,
      lecturerName: x.lecturer_name ?? null,
      title: x.raw_text ?? (constraintsId ? `Constraint #${constraintsId}` : "Constraint"),
      raw_text: x.raw_text ?? null,
      structured_rules: x.structured_rules ?? null,
      is_manually_edited: Boolean(x.is_manually_edited),
      original_raw_text: x.original_raw_text ?? null,
      status: mapOverrideToStatus(x.secretary_override_as_hard),
      is_breaking: breakingIds.has(constraintsId),
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

function createMockApi() {
  let data = [...MOCK_ALL_CONSTRAINTS];

  return {
    list: async ({ lecturerId, breakingOnly }) => {
      return data.filter((r) => {
        if (lecturerId !== "all" && String(r.lecturer_internal_id) !== String(lecturerId)) return false;
        if (breakingOnly && !r.is_breaking) return false;
        return true;
      });
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
    list: async ({ year, number, lecturerId, breakingOnly }) => {
      const [allResp, breakingResp] = await Promise.all([
        apiSearchConstraints({ year, number, lecturerId }),
        apiListBreakingForSemester({ year, number }).catch(() => null),
      ]);
      const breakingList = Array.isArray(breakingResp?.data)
        ? breakingResp.data
        : Array.isArray(breakingResp)
        ? breakingResp
        : [];
      const breakingIds = new Set(
        breakingList.map((b) => b.constraints_id).filter((v) => v !== undefined && v !== null)
      );
      const rows = normalizeAllResponse(allResp, breakingIds);
      return breakingOnly ? rows.filter((r) => r.is_breaking) : rows;
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

export default function SecretaryAllConstraintsPage() {
  const { useMock } = useMockMode();
  const api = useMemo(() => (useMock ? createMockApi() : createRealApi()), [useMock]);

  const [year, setYear] = useState(new Date().getFullYear());
  const [semester, setSemester] = useState(1);
  const [lecturerId, setLecturerId] = useState("all");

  // Default the year filter to the current active semester's year (once).
  const { semesterYear } = useCurrentSemester({ enabled: !useMock });
  const appliedSemesterYearRef = useRef(false);
  useEffect(() => {
    if (!appliedSemesterYearRef.current && semesterYear) {
      setYear(semesterYear);
      appliedSemesterYearRef.current = true;
    }
  }, [semesterYear]);
  const [breakingOnly, setBreakingOnly] = useState(false);

  const [rowsState, setRowsState] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const [deleteTarget, setDeleteTarget] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [notifyDeleteTarget, setNotifyDeleteTarget] = useState(null);

  const [editTarget, setEditTarget] = useState(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editError, setEditError] = useState("");

  const load = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      if (useMock) {
        const list = await api.list({ lecturerId, breakingOnly });
        setRowsState(Array.isArray(list) ? list : []);
        return;
      }
      if (!year || !semester) {
        setRowsState([]);
        return;
      }
      const list = await api.list({
        year: Number(year),
        number: Number(semester),
        lecturerId,
        breakingOnly,
      });
      setRowsState(Array.isArray(list) ? list : []);
    } catch (e) {
      setRowsState([]);
      setError(e?.message || "Failed to load constraints.");
    } finally {
      setIsLoading(false);
    }
  }, [api, useMock, year, semester, lecturerId, breakingOnly]);

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
      setRowsState((curr) =>
        curr.map((r) => (r.id === row.id ? { ...r, status: nextStatus } : r))
      );
      try {
        if (useMock) {
          await api.updateStatus({ rowId: row.id, nextStatus });
          return;
        }
        await api.updateStatus({ constraintsId: row.constraints_id, nextStatus });
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

  // const handleDeleteConfirmed = useCallback(async () => {
  //   if (!deleteTarget) return;
  //   setError("");
  //   setIsDeleting(true);
  //   try {
  //     await handleDelete(deleteTarget);
  //     setDeleteTarget(null);
  //   } finally {
  //     setIsDeleting(false);
  //   }
  // }, [deleteTarget, handleDelete]);

  const handleDeleteConfirmed = useCallback(async () => {
    if (!deleteTarget) return;

    if (deleteTarget.is_breaking) {
      setNotifyDeleteTarget(deleteTarget);
      setDeleteTarget(null);
      return;
    }

    setError("");
    setIsDeleting(true);
    try {
      await handleDelete(deleteTarget);
      setDeleteTarget(null);
    } finally {
      setIsDeleting(false);
    }
  }, [deleteTarget, handleDelete]);

  const handleDeleteWithNotifyChoice = useCallback(
    async ({ notifyLecturer }) => {
      if (!notifyDeleteTarget) return;

      setError("");
      setIsDeleting(true);

      try {
        // TODO: when backend endpoint exists, call notification API here.
        // Example future idea:
        // if (notifyLecturer) {
        //   await api.notifyLecturerAboutDeletedConstraint({
        //     constraintsId: notifyDeleteTarget.constraints_id,
        //   });
        // }

        console.log("Notify lecturer?", notifyLecturer);

        await handleDelete(notifyDeleteTarget);
        setNotifyDeleteTarget(null);
      } finally {
        setIsDeleting(false);
      }
    },
    [notifyDeleteTarget, handleDelete]
  );

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
          curr.map((r) =>
            r.id === editTarget.id ? applyEditedConstraintToRow(r, updated) : r
          )
        );
        setEditTarget(null);
      } catch (e) {
        setEditError(formatEditError(e));
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
          if (!label) return <span className="ac-muted">-</span>;
          return (
            <div className="ac-lecturer-cell">
              <div className="ac-lecturer-avatar">{lecturerInitials(label)}</div>
              <span className="ac-lecturer-name">{label}</span>
            </div>
          );
        },
      },
      {
        header: "Constraint",
        render: (row) => (
          <div className="ac-constraint-cell">
            <span className="ac-constraint-text">{row.title}</span>
            <EditIndicatorBadge
              isEdited={Boolean(row.is_manually_edited)}
              originalRawText={row.original_raw_text}
              className="ac-edit-badge"
            />
          </div>
        ),
      },
      {
        header: "System Interpretation",
        render: (row) => (
          <div className="ac-system-cell">
            <SystemInterpretationCell row={row} />
          </div>
        ),
      },
      {
        header: "Breaking?",
        render: (row) =>
          row.is_breaking ? (
            <span className="ac-breaking-pill">Breaking</span>
          ) : (
            <span className="ac-ok-pill">OK</span>
          ),
      },
      {
        header: "Status",
        render: (row) => (
          <select
            className={`ac-status-select ac-status-${String(row.status).toLowerCase()}`}
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
          <div className="ac-actions-cell">
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
      <div className="ac-head">
        <div>
          <h1 className="ac-h1">All Lecturer Constraints</h1>
          <div className="ac-sub">
            View every lecturer constraint for a semester. Edit structured rules,
            change priority, or delete a constraint. Toggle "Breaking only" to
            focus on conflicts.
          </div>
        </div>

        <div className="ac-filters">
          {useMock ? (
            <label className="ac-filter">
              <span className="ac-label">Lecturer</span>
              <select
                className="ac-select"
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
          ) : (
            <>
              <label className="ac-filter">
                <span className="ac-label">Year</span>
                <YearPicker
                  year={year}
                  onChange={setYear}
                  disabled={isLoading}
                  className="ac-select"
                />
              </label>
              <label className="ac-filter">
                <span className="ac-label">Semester</span>
                <input
                  className="ac-select"
                  type="number"
                  value={semester}
                  onChange={(e) => setSemester(e.target.value)}
                  disabled={isLoading}
                />
              </label>
              <label className="ac-filter">
                <span className="ac-label">Lecturer</span>
                <input
                  className="ac-select"
                  value={lecturerId}
                  onChange={(e) => setLecturerId(e.target.value || "all")}
                  disabled={isLoading}
                  placeholder='Type lecturer id or "all"'
                />
              </label>
            </>
          )}

          <label className="ac-filter ac-toggle">
            <input
              type="checkbox"
              checked={breakingOnly}
              onChange={(e) => setBreakingOnly(e.target.checked)}
              disabled={isLoading}
            />
            <span className="ac-label">Show only breaking</span>
          </label>
        </div>
      </div>

      {error ? <div className="ac-error">{error}</div> : null}

      <DataTable
        columns={columns}
        rows={rowsState}
        rowKey={(r) => r.id}
        emptyText={
          isLoading
            ? "Loading..."
            : "No constraints found for the selected filters."
        }
        // wrapClassName="assignments-table-wrap"
        // tableClassName="assignments-table"
        wrapClassName="ac-table-wrap"
        tableClassName="ac-table"
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
      <ConfirmModal
        open={Boolean(notifyDeleteTarget)}
        title="Notify lecturer?"
        message="This is a breaking constraint. Do you want to notify the lecturer that this constraint was deleted?"
        confirmText="Delete & Notify"
        cancelText="Delete only"
        onCancel={() => handleDeleteWithNotifyChoice({ notifyLecturer: false })}
        onConfirm={() => handleDeleteWithNotifyChoice({ notifyLecturer: true })}
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
