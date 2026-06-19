// src/pages/SecretaryAssignmentsPage.jsx
import { useCallback, useEffect, useMemo, useState } from "react";
import "./SchedulePage.css";
import "../../components/ConfirmModal.css";
import { useMockMode } from "../../context/MockModeContext.jsx";
import {
  mockGetSemesterInfo,
  mockGetSolverStatus,
  mockGetScheduleDetails,
} from "./secretaryScheduleMock";
import DataTable from "../../components/DataTable.jsx";
import {
  BookOpen,
  CalendarDays,
  Clock3,
  Download,
  FileText,
  FileSpreadsheet,
  GraduationCap,
  Search,
  UserRound,
  Building2,
  RotateCcw,
} from "lucide-react";


const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const SECRETARY_PREFIX = import.meta.env.VITE_API_PREFIX_SECRETARY || "/secretary";
const API_BASE = API_BASE_URL + SECRETARY_PREFIX;

const POLL_INTERVAL_MS = 5000;

const DAY_LABELS = { 1: "Sunday", 2: "Monday", 3: "Tuesday", 4: "Wednesday", 5: "Thursday", 6: "Friday" };
const DAY_OPTIONS = [
  { value: "ALL", label: "All days" },
  { value: "1", label: "Sunday" }, { value: "2", label: "Monday" }, { value: "3", label: "Tuesday" },
  { value: "4", label: "Wednesday" }, { value: "5", label: "Thursday" }, { value: "6", label: "Friday" },
];

function getToken() { return localStorage.getItem("access_token"); }
function toTimeRange(s, e) { return s && e ? `${s} - ${e}` : s || "—"; }
function toDayLabel(d) { return DAY_LABELS[d] || `Day ${d}`; }
function normalizeText(v) { return String(v ?? "").toLowerCase().trim(); }
function toShortDayLabel(day) {
  return String(toDayLabel(day)).slice(0, 3).toUpperCase();
}

function resetAssignmentFilters(setSearch, setFilters) {
  setSearch("");
  setFilters({
    lecturer: "ALL",
    day: "ALL",
    department: "ALL",
    yearLevel: "ALL",
  });
}

// Build a CSV (client-side) from the currently displayed rows. Used as a
// fallback in mock mode where there is no backend to hit.
function buildClientCsv(rows) {
  const headers = ["Course Name", "Course Number", "Group", "Lecturer", "Day", "Start Time", "End Time"];
  const escape = (v) => {
    const s = String(v ?? "");
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [headers.join(",")];
  rows.forEach((s) => {
    lines.push(
      [
        s.course_name,
        s.course_number,
        s.group_number,
        s.lecturer_name,
        toDayLabel(s.day_of_week),
        s.start_time ? String(s.start_time).slice(0, 5) : "",
        s.end_time ? String(s.end_time).slice(0, 5) : "",
      ]
        .map(escape)
        .join(",")
    );
  });
  return "\ufeff" + lines.join("\n");
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export default function SecretaryAssignmentsPage() {
  const { useMock } = useMockMode();
  const [semester, setSemester] = useState(null);
  const [solverStatus, setSolverStatus] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  // const [setIsPolling] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  // const [setError] = useState("");
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  // const [filters, setFilters] = useState({ lecturer: "ALL", day: "ALL" });
  const [filters, setFilters] = useState({lecturer: "ALL", day: "ALL", department: "ALL", yearLevel: "ALL"});
  const [sort, setSort] = useState({ key: "course_name", dir: "asc" });

  const [exportOpen, setExportOpen] = useState(false);
  const [isExporting, setIsExporting] = useState(false);

  function sortIndicator(key) {
    if (sort.key !== key) return "";
    return sort.dir === "asc" ? " ▲" : " ▼";
  }

  const scheduleId = useMemo(() => solverStatus?.schedule_id || null, [solverStatus]);

  const fetchSolverStatus = useCallback(async (year, num) => {
    // if (useMock) return null;
    if (useMock) return await mockGetSolverStatus(year, num);
    const res = await fetch(`${API_BASE}/dashboard/solver_status?semester_year=${year}&semester_number=${num}`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    if (!res.ok) throw new Error("Failed to load solver status");
    return await res.json();
  }, [useMock]);

  const fetchDetails = useCallback(async (id) => {
    // if (useMock) return [];
    if (useMock) return await mockGetScheduleDetails(id);
    const res = await fetch(`${API_BASE}/schedules/${id}/details`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    if (!res.ok) throw new Error("Failed to load details");
    return await res.json();
  }, [useMock]);

  useEffect(() => {
    async function boot() {
      setIsLoading(true);
      try {
        if (useMock) {
          // setSemester({ semester_year: 2026, semester_number: 1 });
          const sem = await mockGetSemesterInfo();
          setSemester(sem);
        } else {
          const res = await fetch(`${API_BASE}/dashboard/semester_info`, {
            headers: { Authorization: `Bearer ${getToken()}` },
          });
          const data = await res.json();
          if (data?.semester_year) setSemester(data);
        }
      } catch (e) { setError(e.message); }
      finally { setIsLoading(false); }
    }
    boot();
  }, [useMock]);

  useEffect(() => {
    if (!semester) return;
    let intervalId = null;
    let alive = true;

    async function check() {
      try {
        const status = await fetchSolverStatus(semester.semester_year, semester.semester_number);
        if (!alive) return;
        setSolverStatus(status);

        if (status?.status === "solved" && status.schedule_id) {
          const d = await fetchDetails(status.schedule_id);
          if (alive) setSessions(d);
        }

        if (status?.status === "pending") {
          setIsPolling(true);
          intervalId = setInterval(async () => {
            const next = await fetchSolverStatus(semester.semester_year, semester.semester_number);
            if (!alive) return;
            setSolverStatus(next);
            if (next?.status !== "pending") {
              clearInterval(intervalId);
              setIsPolling(false);
              if (next?.status === "solved") {
                const d = await fetchDetails(next.schedule_id);
                setSessions(d);
              }
            }
          }, POLL_INTERVAL_MS);
        }
      } catch (e) { setError(e.message); }
    }
    check();
    return () => { alive = false; if (intervalId) clearInterval(intervalId); };
  }, [semester, fetchSolverStatus, fetchDetails]);

  const lecturerOptions = useMemo(() => {
    const uniq = new Set(sessions.map(s => s.lecturer_name).filter(Boolean));
    return ["ALL", ...Array.from(uniq).sort()];
  }, [sessions]);

  const departmentOptions = useMemo(() => {
    const ids = new Set();
    (sessions || []).forEach((s) => {
      const cohorts = Array.isArray(s.cohorts) ? s.cohorts : [];
      cohorts.forEach((c) => {
        if (c?.target_department_id != null) ids.add(String(c.target_department_id));
      });
    });
    return ["ALL", ...Array.from(ids).sort((a, b) => Number(a) - Number(b))];
  }, [sessions]);

  const yearLevelOptions = useMemo(() => {
    const levels = new Set();
    (sessions || []).forEach((s) => {
      const cohorts = Array.isArray(s.cohorts) ? s.cohorts : [];
      cohorts.forEach((c) => {
        if (c?.target_year_level != null) levels.add(String(c.target_year_level));
      });
    });
    return ["ALL", ...Array.from(levels).sort((a, b) => Number(a) - Number(b))];
  }, [sessions]);


  const filteredRows = useMemo(() => {
    const q = normalizeText(search);
    return (sessions || [])
      .filter(s => {
        if (filters.lecturer !== "ALL" && s.lecturer_name !== filters.lecturer) return false;
        if (filters.day !== "ALL" && String(s.day_of_week) !== String(filters.day)) return false;
          const cohorts = Array.isArray(s.cohorts) ? s.cohorts : [];
        if (filters.department !== "ALL") {
          const hasDept = cohorts.some((c) => String(c.target_department_id) === String(filters.department));
          if (!hasDept) return false;
        }
        if (filters.yearLevel !== "ALL") {
          const hasYear = cohorts.some((c) => String(c.target_year_level) === String(filters.yearLevel));
          if (!hasYear) return false;
        }
        if (!q) return true;
        return [s.course_name, s.course_number, s.lecturer_name].some(v => normalizeText(v).includes(q));
      })
      .sort((a, b) => {
        const dir = sort.dir === "asc" ? 1 : -1;
        const av = a[sort.key], bv = b[sort.key];
        return (typeof av === 'number' ? av - bv : String(av).localeCompare(String(bv))) * dir;
      });
  }, [sessions, filters, search, sort]);

  const onSort = useCallback((key) => {
    setSort((prev) => ({
      key,
      dir: prev.key === key && prev.dir === "asc" ? "desc" : "asc",
    }));
  }, []);

  const handleExport = useCallback(
    async (format) => {
      setError("");
      setIsExporting(true);
      try {
        const baseName = `schedule_${scheduleId || "assignments"}_assignments`;

        if (useMock) {
          // No backend in mock mode: CSV is generated client-side; PDF needs the API.
          if (format === "csv") {
            const csv = buildClientCsv(filteredRows);
            triggerDownload(new Blob([csv], { type: "text/csv;charset=utf-8" }), `${baseName}.csv`);
          } else {
            setError("PDF export is only available with the live backend.");
          }
          return;
        }

        if (!scheduleId) {
          setError("No schedule available to export.");
          return;
        }

        const res = await fetch(`${API_BASE}/schedules/${scheduleId}/export?format=${format}`, {
          headers: { Authorization: `Bearer ${getToken()}` },
        });
        if (!res.ok) throw new Error(`Export failed (${res.status})`);

        const blob = await res.blob();
        const ext = format === "pdf" ? "pdf" : "csv";
        triggerDownload(blob, `${baseName}.${ext}`);
      } catch (e) {
        setError(e.message || "Export failed.");
      } finally {
        setIsExporting(false);
        setExportOpen(false);
      }
    },
    [useMock, scheduleId, filteredRows]
  );

  // const columns = useMemo(() => [
  //   {
  //     id: "course",
  //     header: "Course",
  //     sortKey: "course_name",
  //     render: (s) => (
  //       <>
  //         <strong>{s.course_name}</strong> ({s.course_number})
  //       </>
  //     ),
  //   },
  //   {
  //     id: "lecturer",
  //     header: "Lecturer",
  //     sortKey: "lecturer_name",
  //     key: "lecturer_name",
  //   },
  //   {
  //     id: "day",
  //     header: "Day",
  //     sortKey: "day_of_week",
  //     render: (s) => toDayLabel(s.day_of_week),
  //   },
  //   {
  //     id: "time",
  //     header: "Time",
  //     sortKey: "start_time",
  //     render: (s) => toTimeRange(s.start_time, s.end_time),
  //   },
  // ], []);
  const columns = useMemo(() => [
  {
    id: "course",
    header: "Course",
    sortKey: "course_name",
    render: (s) => (
      <div className="assign-course-cell">
        <div className="assign-course-icon">
          <BookOpen size={18} strokeWidth={2.2} />
        </div>
        <div>
          <div className="assign-course-name">{s.course_name}</div>
          <div className="assign-course-number">{s.course_number}</div>
        </div>
      </div>
    ),
  },
  {
    id: "lecturer",
    header: "Lecturer",
    sortKey: "lecturer_name",
    render: (s) => (
      <div className="assign-lecturer-cell">
        <div className="assign-lecturer-avatar">
          {String(s.lecturer_name || "?")
            .replace(/^Dr\.?\s*/i, "")
            .split(" ")
            .map((p) => p[0])
            .join("")
            .slice(0, 2)}
        </div>
        <span>{s.lecturer_name}</span>
      </div>
    ),
  },
  {
    id: "day",
    header: "Day",
    sortKey: "day_of_week",
    render: (s) => (
      <div className="assign-day-cell">
        <span className="assign-day-pill">{toShortDayLabel(s.day_of_week)}</span>
        <span>{toDayLabel(s.day_of_week)}</span>
      </div>
    ),
  },
  {
    id: "time",
    header: "Time",
    sortKey: "start_time",
    render: (s) => (
      <div className="assign-time-cell">
        <Clock3 size={16} strokeWidth={2.2} />
        <span>{toTimeRange(s.start_time, s.end_time)}</span>
      </div>
    ),
  },
], []);


  return (
    <div className="schedule-page">
      <div className="schedule-inner">
        <header className="schedule-header assignments-header">
          <button
            type="button"
            className="assign-export-btn"
            onClick={() => setExportOpen(true)}
            disabled={isExporting}
          >
            <Download size={17} strokeWidth={2.2} />
            <span>Export</span>
          </button>
          <div>
            <h1 className="schedule-title">Schedule Assignments</h1>
            <p className="schedule-subtitle">
              {semester ? `Semester ${semester.semester_number} / ${semester.semester_year}` : "Loading..."}
              {scheduleId && ` (Schedule ID: ${scheduleId})`}
            </p>
          </div>
        </header>

        {isLoading ? <div className="spinner" /> : (
          <>
            {solverStatus?.status === "none" && (
              <div className="schedule-empty-screen">
                <p>No schedule exists yet. Generate it from the Schedule page.</p>
              </div>
            )}

            {solverStatus?.status === "pending" && (
              <div className="schedule-empty-screen">
                <div className="spinner" />
                <p>Generating optimal schedule...</p>
              </div>
            )}

            {solverStatus?.status === "solved" && (
              <>
                <div className="schedule-toolbar">
                  <div className="filters-bar">
                    <div className="filter-field">
                      <label>Search</label>
                      {/* <input
                        className="search-input"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder="Search..."
                      /> */}
                      <div className="assign-input-wrap">
                        <Search size={17} strokeWidth={2.2} />
                        <input
                          className="search-input"
                          value={search}
                          onChange={(e) => setSearch(e.target.value)}
                          placeholder="Search..."
                        />
                      </div>
                    </div>

                    <div className="filter-field">
                      <label>Lecturer</label>
                      <select
                        value={filters.lecturer}
                        onChange={(e) => setFilters((p) => ({ ...p, lecturer: e.target.value }))}
                        disabled={lecturerOptions.length <= 1}
                      >
                        {lecturerOptions.map((name) => (
                          <option key={name} value={name}>
                            {name === "ALL" ? "All Lecturers" : name}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="filter-field">
                      <label>Day</label>
                      <select
                        value={filters.day}
                        onChange={(e) => setFilters((p) => ({ ...p, day: e.target.value }))}
                      >
                        {DAY_OPTIONS.map((d) => (
                          <option key={d.value} value={d.value}>
                            {d.label}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="filter-field">
                      <label>Department</label>
                      <select
                        value={filters.department}
                        onChange={(e) => setFilters((p) => ({ ...p, department: e.target.value }))}
                        disabled={departmentOptions.length <= 1}
                      >
                        {departmentOptions.map((id) => (
                          <option key={id} value={id}>
                            {id === "ALL" ? "All departments" : `${id}`}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className="filter-field">
                      <label>Year</label>
                      <select
                        value={filters.yearLevel}
                        onChange={(e) => setFilters((p) => ({ ...p, yearLevel: e.target.value }))}
                        disabled={yearLevelOptions.length <= 1}
                      >
                        {yearLevelOptions.map((y) => (
                          <option key={y} value={y}>
                            {y === "ALL" ? "All years" : `Year ${y}`}
                          </option>
                        ))}
                      </select>
                    </div>
                    <button
                      type="button"
                      className="assign-clear-btn"
                      onClick={() => resetAssignmentFilters(setSearch, setFilters)}
                    >
                      <RotateCcw size={16} strokeWidth={2.2} />
                      <span>Clear filters</span>
                    </button>
                  </div>
                </div>


                {/* <div className="assignments-table-wrap">
                  <table className="assignments-table">
                    <thead>
                      <tr>
                        <th
                          onClick={() =>
                            setSort((prev) => ({
                              key: "course_name",
                              dir: prev.key === "course_name" && prev.dir === "asc" ? "desc" : "asc",
                            }))
                          }
                        >
                          Course{sortIndicator("course_name")}
                        </th>

                        <th>Lecturer</th>
                        <th>Day</th>
                        <th>Time</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredRows.map((s) => (
                        <tr key={s.session_id || `${s.course_number}-${s.group_number}`}>
                          <td><strong>{s.course_name}</strong> ({s.course_number})</td>
                          <td>{s.lecturer_name}</td>
                          <td>{toDayLabel(s.day_of_week)}</td>
                          <td>{toTimeRange(s.start_time, s.end_time)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div> */}
                <DataTable
                  columns={columns}
                  rows={filteredRows}
                  wrapClassName="assign-modern-table-wrap"
                  tableClassName="assign-modern-table"
                  rowKey={(s) => s.session_id || `${s.course_number}-${s.group_number}`}
                  sort={sort}
                  onSort={onSort}
                  emptyText="No sessions match your filters"
                />

              </>
            )}
          </>
        )}
      </div>

      {exportOpen && (
        <div className="cm-backdrop" onClick={() => !isExporting && setExportOpen(false)} role="presentation">
          <div className="cm-card" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
            <div className="cm-title">Export assignments</div>
            <div className="cm-message">Choose a format to download the schedule assignments.</div>

            <div className="assign-export-options">
              <button
                type="button"
                className="assign-export-option"
                onClick={() => handleExport("csv")}
                disabled={isExporting}
              >
                <FileSpreadsheet size={20} strokeWidth={2.2} />
                <span>CSV</span>
              </button>
              <button
                type="button"
                className="assign-export-option"
                onClick={() => handleExport("pdf")}
                disabled={isExporting}
              >
                <FileText size={20} strokeWidth={2.2} />
                <span>PDF</span>
              </button>
            </div>

            <div className="cm-actions">
              <button
                type="button"
                className="button button-secondary"
                onClick={() => setExportOpen(false)}
                disabled={isExporting}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}