// src/pages/Fairness/SecretaryFairnessPage.jsx

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "./FairnessPage.css";

import DataTable from "../../components/DataTable.jsx";
import YearPicker from "../../components/YearPicker.jsx";
import useCurrentSemester from "../../hooks/useCurrentSemester.js";
import { useMockMode } from "../../context/MockModeContext.jsx";
import {
  BookOpen,
  Check,
  ClipboardList,
  Search,
  UsersRound,
  X,
} from "lucide-react";

/* ==============================
   CONSTANTS
============================== */

const DAY_NAMES = {
  1: "SUNDAY",
  2: "MONDAY",
  3: "TUESDAY",
  4: "WEDNESDAY",
  5: "THURSDAY",
  6: "FRIDAY",
};

const SCHEDULE_STATUS_LABEL = {
  draft: "Draft",
  published: "Published",
  none: "None",
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const SECRETARY_PREFIX = import.meta.env.VITE_API_PREFIX_SECRETARY || "/secretary";
const API_BASE = API_BASE_URL + SECRETARY_PREFIX;

/* ==============================
   MOCK DATA (used when mock mode is on)
============================== */

const MOCK_FAIRNESS_RESPONSE = {
  status: "success",
  semester_year: 2026,
  semester_number: 1,
  schedule_id: 12,
  schedule_status: "published",
  data: [
    {
      lecturer_internal_id: 101,
      lecturer_name: "Dana Cohen",
      courses_count: 3,
      total_atomics: 4,
      broken_atomics: 1,
      satisfied_atomics: 3,
      hard_total: 2,
      soft_total: 2,
      hard_broken: 1,
      soft_broken: 0,
      fairness_score: 0.75,
      is_fair: false,
      atomic_details: [
        {
          constraints_id: 42,
          raw_text: "I cannot teach on Mondays 16-20",
          atomic_index: 0,
          type: "block",
          days: [2],
          time_slot: { start_hour: 16, end_hour: 20 },
          is_hard: true,
          is_broken: true,
        },
        {
          constraints_id: 42,
          raw_text: "Prefer mornings",
          atomic_index: 1,
          type: "preference",
          days: [1, 3],
          time_slot: { start_hour: 8, end_hour: 12 },
          is_hard: false,
          is_broken: false,
        },
        {
          constraints_id: 42,
          raw_text: "No Friday classes",
          atomic_index: 2,
          type: "block",
          days: [6],
          time_slot: null,
          is_hard: true,
          is_broken: false,
        },
        {
          constraints_id: 42,
          raw_text: "Prefer mornings",
          atomic_index: 3,
          type: "preference",
          days: [4],
          time_slot: { start_hour: 8, end_hour: 12 },
          is_hard: false,
          is_broken: false,
        },
      ],
    },
    {
      lecturer_internal_id: 102,
      lecturer_name: "Maya Levi",
      courses_count: 2,
      total_atomics: 2,
      broken_atomics: 0,
      satisfied_atomics: 2,
      hard_total: 1,
      soft_total: 1,
      hard_broken: 0,
      soft_broken: 0,
      fairness_score: 1.0,
      is_fair: true,
      atomic_details: [
        {
          constraints_id: 55,
          raw_text: "Block Tuesday afternoon",
          atomic_index: 0,
          type: "block",
          days: [3],
          time_slot: { start_hour: 14, end_hour: 18 },
          is_hard: true,
          is_broken: false,
        },
        {
          constraints_id: 55,
          raw_text: "Prefer no Sunday morning",
          atomic_index: 1,
          type: "preference",
          days: [1],
          time_slot: { start_hour: 8, end_hour: 10 },
          is_hard: false,
          is_broken: false,
        },
      ],
    },
    {
      lecturer_internal_id: 103,
      lecturer_name: "Sara Doron",
      courses_count: 1,
      total_atomics: 0,
      broken_atomics: 0,
      satisfied_atomics: 0,
      hard_total: 0,
      soft_total: 0,
      hard_broken: 0,
      soft_broken: 0,
      fairness_score: 1.0,
      is_fair: true,
      atomic_details: [],
    },
  ],
  count: 3,
};

/* ==============================
   HELPERS
============================== */

function pad2(n) {
  return String(n ?? 0).padStart(2, "0");
}

function formatTimeSlot(ts) {
  if (!ts) return "all day";
  const from = `${pad2(ts.start_hour)}:${pad2(ts.start_minute ?? 0)}`;
  const to = `${pad2(ts.end_hour)}:${pad2(ts.end_minute ?? 0)}`;
  return `${from} - ${to}`;
}

function formatDays(days) {
  if (!Array.isArray(days) || days.length === 0) return "ANY";
  return days.map((d) => DAY_NAMES[d] || `DAY_${d}`).join(", ");
}

function normalizeText(v) {
  return String(v ?? "").toLowerCase().trim();
}

function lecturerInitials(name) {
  return String(name || "?")
    .split(" ")
    .map((p) => p[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

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
    const message =
      (detail && typeof detail === "object" ? JSON.stringify(detail) : detail) ||
      data?.message ||
      `Request failed (${res.status})`;
    throw new Error(message);
  }
  return data;
}

async function apiFetchFairness({ year, number }) {
  return fetchJson(`${API_BASE}/fairness/${year}/${number}`, { method: "GET" });
}

/* ==============================
   PAGE
============================== */

export default function SecretaryFairnessPage() {
  const { useMock } = useMockMode();

  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [number, setNumber] = useState(1);

  // Default the year filter to the current active semester's year (once).
  const { semesterYear } = useCurrentSemester({ enabled: !useMock });
  const appliedSemesterYearRef = useRef(false);
  useEffect(() => {
    if (!appliedSemesterYearRef.current && semesterYear) {
      setYear(semesterYear);
      appliedSemesterYearRef.current = true;
    }
  }, [semesterYear]);

  const [rows, setRows] = useState([]);
  const [scheduleId, setScheduleId] = useState(null);
  const [scheduleStatus, setScheduleStatus] = useState("none");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const [selectedLecturerId, setSelectedLecturerId] = useState(null);
  const [sort, setSort] = useState({ key: "lecturer_name", dir: "asc" });
  const [search, setSearch] = useState("");
  const [onlyBroken, setOnlyBroken] = useState(false);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError("");
    try {
      const payload = useMock
        ? MOCK_FAIRNESS_RESPONSE
        : await apiFetchFairness({ year: Number(year), number: Number(number) });

      const list = Array.isArray(payload?.data) ? payload.data : [];
      setRows(list);
      setScheduleId(payload?.schedule_id ?? null);
      setScheduleStatus(payload?.schedule_status ?? "none");
    } catch (e) {
      setRows([]);
      setScheduleId(null);
      setScheduleStatus("none");
      setError(e?.message || "Failed to load fairness report.");
    } finally {
      setIsLoading(false);
    }
  }, [useMock, year, number]);

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

  useEffect(() => {
    if (selectedLecturerId == null) return;
    const stillThere = rows.some((r) => r.lecturer_internal_id === selectedLecturerId);
    if (!stillThere) setSelectedLecturerId(null);
  }, [rows, selectedLecturerId]);

  const selected = useMemo(
    () => rows.find((r) => r.lecturer_internal_id === selectedLecturerId) || null,
    [rows, selectedLecturerId]
  );

  const onSort = useCallback((key) => {
    setSort((prev) => ({
      key,
      dir: prev.key === key && prev.dir === "asc" ? "desc" : "asc",
    }));
  }, []);

  const handleSelect = useCallback((r) => {
    setSelectedLecturerId(r.lecturer_internal_id);
  }, []);

  const columns = useMemo(
    () => [
      {
        id: "name",
        header: "Lecturer",
        sortKey: "lecturer_name",
        // render: (r) => (
        //   <span className={r.hard_broken > 0 ? "severity-row-hard" : ""}>
        //     {r.lecturer_name}
        //   </span>
        // ),
        render: (r) => (
          <div className="fairness-lecturer-cell">
            <span className={`fairness-avatar ${r.hard_broken > 0 ? "fairness-avatar-danger" : ""}`}>
              {lecturerInitials(r.lecturer_name)}
            </span>
            <span className={r.hard_broken > 0 ? "severity-row-hard" : ""}>
              {r.lecturer_name}
            </span>
          </div>
        ),
      },
      { id: "courses", header: "# Courses", sortKey: "courses_count", key: "courses_count" },
      { id: "total", header: "Total", sortKey: "total_atomics", key: "total_atomics" },
      {
        id: "broken",
        header: "Broken",
        sortKey: "broken_atomics",
        render: (r) =>
          r.broken_atomics > 0 ? (
            <span className="badge badge-broken-soft">{r.broken_atomics}</span>
          ) : (
            <span className="badge badge-satisfied">0</span>
          ),
      },
      {
        id: "satisfied",
        header: "Satisfied",
        sortKey: "satisfied_atomics",
        render: (r) => (
          <span className="badge badge-satisfied">{r.satisfied_atomics}</span>
        ),
      },
      {
        id: "hard_broken",
        header: "Hard broken",
        sortKey: "hard_broken",
        render: (r) =>
          r.hard_broken > 0 ? (
            <span className="badge badge-broken-hard">{r.hard_broken}</span>
          ) : (
            <span className="muted-text">0</span>
          ),
      },
      {
        id: "score",
        header: "Score",
        sortKey: "fairness_score",
        render: (r) =>
          // r.fairness_score != null ? r.fairness_score.toFixed(2) : "—",
          r.fairness_score != null ? (
          <div className="fairness-score-cell">
            <span>{r.fairness_score.toFixed(2)}</span>
            <span
              className={`fairness-score-bar ${
                r.fairness_score < 1 ? "fairness-score-warning" : "fairness-score-good"
              }`}
            />
          </div>
        ) : "—",
      },
    ],
    []
  );

  const filteredRows = useMemo(() => {
    const q = normalizeText(search);
    return rows.filter((r) => {
      if (onlyBroken && !(r.broken_atomics > 0)) return false;
      if (q && !normalizeText(r.lecturer_name).includes(q)) return false;
      return true;
    });
  }, [rows, search, onlyBroken]);

  const sortedRows = useMemo(() => {
    const dir = sort.dir === "asc" ? 1 : -1;
    return [...filteredRows].sort((a, b) => {
      const av = a[sort.key];
      const bv = b[sort.key];
      if (typeof av === "number" && typeof bv === "number") return (av - bv) * dir;
      if (typeof av === "boolean" && typeof bv === "boolean")
        return (av === bv ? 0 : av ? 1 : -1) * dir;
      return String(av ?? "").localeCompare(String(bv ?? "")) * dir;
    });
  }, [filteredRows, sort]);

  const brokenAtomics = useMemo(
    () => (selected?.atomic_details || []).filter((a) => a.is_broken),
    [selected]
  );
  const satisfiedAtomics = useMemo(
    () => (selected?.atomic_details || []).filter((a) => !a.is_broken),
    [selected]
  );
  const fairnessSummary = useMemo(() => {
    return rows.reduce(
      (acc, r) => ({
        lecturers: acc.lecturers + 1,
        courses: acc.courses + Number(r.courses_count || 0),
        broken: acc.broken + Number(r.broken_atomics || 0),
        satisfied: acc.satisfied + Number(r.satisfied_atomics || 0),
      }),
      { lecturers: 0, courses: 0, broken: 0, satisfied: 0 }
    );
  }, [rows]);

  return (
    <div className="schedule-page">
      <div className="schedule-inner">
        <header className="schedule-header">
          <div>
            <h1 className="schedule-title">Fairness</h1>
            <p className="schedule-subtitle">
              For each lecturer, see how many of their atomic constraints were
              satisfied vs broken by the latest schedule.
            </p>
          </div>
        </header>
{/* 
        <div className="card filter-bar">
          <div className="filter-field">
            <label>Year</label>
            <input
              type="number"
              className="search-input"
              value={year}
              min={2000}
              max={2100}
              onChange={(e) => setYear(e.target.value)}
            />
          </div>
          <div className="filter-field">
            <label>Semester</label>
            <select
              className="search-input"
              value={number}
              onChange={(e) => setNumber(e.target.value)}
            >
              <option value={1}>1</option>
              <option value={2}>2</option>
              <option value={3}>3</option>
            </select>
          </div>
          <div className="filter-field">
            <label>Latest schedule</label>
            <div className="muted-text">
              {scheduleId
                ? `#${scheduleId} (${SCHEDULE_STATUS_LABEL[scheduleStatus] || scheduleStatus})`
                : "None yet for this semester"}
            </div>
          </div>
        </div> */}
        <div className="card fairness-top-card">
          <div className="fairness-top-filters">
            <div className="filter-field">
              <label>Year</label>
              <YearPicker year={year} onChange={setYear} />
            </div>

            <div className="filter-field">
              <label>Semester</label>
              <select
                className="search-input"
                value={number}
                onChange={(e) => setNumber(e.target.value)}
              >
                <option value={1}>1</option>
                <option value={2}>2</option>
                <option value={3}>3</option>
              </select>
            </div>

            <div className="fairness-latest">
              <span>Latest schedule</span>
              <strong>
                {scheduleId
                  ? `#${scheduleId} (${SCHEDULE_STATUS_LABEL[scheduleStatus] || scheduleStatus})`
                  : "None yet"}
              </strong>
            </div>
          </div>

          <div className="fairness-stats">
            <div className="fairness-stat">
              <UsersRound size={21} />
              <div>
                <strong>{fairnessSummary.lecturers}</strong>
                <span>Lecturers</span>
              </div>
            </div>

            <div className="fairness-stat">
              <BookOpen size={21} />
              <div>
                <strong>{fairnessSummary.courses}</strong>
                <span>Courses</span>
              </div>
            </div>

            <div className="fairness-stat fairness-stat-danger">
              <X size={21} />
              <div>
                <strong>{fairnessSummary.broken}</strong>
                <span>Broken</span>
              </div>
            </div>

            <div className="fairness-stat fairness-stat-good">
              <Check size={21} />
              <div>
                <strong>{fairnessSummary.satisfied}</strong>
                <span>Satisfied</span>
              </div>
            </div>
          </div>
        </div>

        {error && (
          <div className="card error-banner" role="alert">
            {error}
          </div>
        )}

        <div className="fairness-layout">
          <div className="card">
            <h2 className="card-title">Lecturers</h2>

            {/* <div className="filter-field">
              <label>Search lecturer</label>
              <input
                className="search-input"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Type a lecturer name..."
              />
            </div> */}

            {/* <label className="fairness-hard-toggle">
              <input
                type="checkbox"
                checked={onlyBroken}
                onChange={(e) => setOnlyBroken(e.target.checked)}
              />
              Only show lecturers with broken constraints
            </label> */}
            <div className="fairness-lecturer-tools">
              <div className="fairness-search-wrap">
                <Search size={17} strokeWidth={2.2} />
                <input
                  className="search-input"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search lecturer..."
                />
              </div>

              <label className="fairness-hard-toggle">
                <input
                  type="checkbox"
                  checked={onlyBroken}
                  onChange={(e) => setOnlyBroken(e.target.checked)}
                />
                Show only with broken constraints
              </label>
            </div>

            <DataTable
              columns={columns}
              rows={sortedRows}
              rowKey={(r) => r.lecturer_internal_id}
              sort={sort}
              onSort={onSort}
              onRowClick={handleSelect}
              emptyText={isLoading ? "Loading..." : "No lecturers"}
              wrapClassName="fairness-table-wrap"
              tableClassName="fairness-table"
            />
          </div>

          <div className="card">
            <h2 className="card-title">Constraints</h2>

            {!selected ? (
            <div className="fairness-empty-state">
              <ClipboardList size={72} strokeWidth={1.7} />
              <h3>No lecturer selected</h3>
              <p>Choose a lecturer from the list to see their constraint breakdown and details.</p>
            </div>
            ) : (
              <>
                <div className="fairness-selected-name">{selected.lecturer_name}</div>
                <div className="muted-text" style={{ marginBottom: 12 }}>
                  {selected.broken_atomics} broken ({selected.hard_broken} hard,{" "}
                  {selected.soft_broken} soft) · {selected.satisfied_atomics} satisfied
                  / total {selected.total_atomics} · score{" "}
                  {selected.fairness_score.toFixed(2)}
                </div>

                <AtomicSection
                  title="Broken"
                  badgeClass="badge-broken-hard"
                  atomics={brokenAtomics}
                  emptyText="No broken constraints for this lecturer."
                />

                <AtomicSection
                  title="Satisfied"
                  badgeClass="badge-satisfied"
                  atomics={satisfiedAtomics}
                  emptyText="No satisfied constraints for this lecturer."
                />
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ==============================
   SUB-COMPONENTS
============================== */

function AtomicSection({ title, badgeClass, atomics, emptyText }) {
  return (
    <div className="fairness-section">
      <div className="fairness-section-header">
        <span className={`badge ${badgeClass}`}>{title}</span>
        <span className="muted-text">{atomics.length}</span>
      </div>

      {atomics.length === 0 ? (
        <div className="muted-text">{emptyText}</div>
      ) : (
        <table className="assignments-table">
          <thead>
            <tr>
              <th>Constraint</th>
              <th>Type</th>
              <th>Day(s)</th>
              <th>Time</th>
              <th>Priority</th>
            </tr>
          </thead>
          <tbody>
            {atomics.map((a) => (
              <tr key={`${a.constraints_id}-${a.atomic_index}`}>
                <td>{a.raw_text || `Constraint #${a.constraints_id ?? "?"}`}</td>
                <td>{a.type || "—"}</td>
                <td>{formatDays(a.days)}</td>
                <td>{formatTimeSlot(a.time_slot)}</td>
                <td>
                  <span
                    className={`badge ${a.is_hard ? "badge-hard" : "badge-soft"}`}
                  >
                    {a.is_hard ? "Required" : "Preferred"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
