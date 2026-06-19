import { useCallback, useEffect, useMemo, useState } from "react";
import "../Schedule/SchedulePage.css";

import NoScheduleState from "../../components/NoScheduleState";
import WeeklyScheduleGrid from "../../components/WeeklyScheduleGrid";
import EditableWeeklyScheduleGrid from "../../components/EditableWeeklyScheduleGrid.jsx";
import ConfirmModal from "../../components/ConfirmModal.jsx";
import { useMockMode } from "../../context/MockModeContext.jsx";
import {
  mockGetSemesterInfo,
  mockGetSolverStatus,
  mockGetScheduleDetails,
} from "./secretaryScheduleMock.js";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const SECRETARY_PREFIX = import.meta.env.VITE_API_PREFIX_SECRETARY || "/secretary";
const API_BASE = `${API_BASE_URL}${SECRETARY_PREFIX}`;

const POLL_INTERVAL_MS = 5000;

const DAY_OPTIONS = [
  { value: "ALL", label: "All days" },
  { value: "1", label: "Sunday" },
  { value: "2", label: "Monday" },
  { value: "3", label: "Tuesday" },
  { value: "4", label: "Wednesday" },
  { value: "5", label: "Thursday" },
  { value: "6", label: "Friday" },
];

const SEMESTER_LABELS = { 1: "Fall", 2: "Spring", 3: "Summer" };
const ALL_VALUE = "ALL";

function getToken() {
  return localStorage.getItem("access_token");
}

function MultiSelectDropdown({
  label,
  options,
  selectedValues,
  onChange,
  allLabel,
  formatLabel = (value) => value,
  disabled = false,
}) {
  const [open, setOpen] = useState(false);

  const selected = Array.isArray(selectedValues) ? selectedValues : [ALL_VALUE];
  const isAllSelected = selected.includes(ALL_VALUE);

  const buttonText = isAllSelected
    ? allLabel
    : selected.map(formatLabel).join(", ");

  const toggleValue = (value) => {
    if (value === ALL_VALUE) {
      onChange([ALL_VALUE]);
      return;
    }

    const withoutAll = selected.filter((item) => item !== ALL_VALUE);
    const exists = withoutAll.includes(value);

    const next = exists
      ? withoutAll.filter((item) => item !== value)
      : [...withoutAll, value];

    onChange(next.length === 0 ? [ALL_VALUE] : next);
  };

  return (
    <div className="filter-field schedule-multi-field">
      <label>{label}</label>

      <button
        type="button"
        className="schedule-multi-trigger"
        onClick={() => setOpen((prev) => !prev)}
        disabled={disabled}
      >
        <span>{buttonText}</span>
        <span className="schedule-multi-chevron">{open ? "▴" : "▾"}</span>
      </button>

      {open && (
        <div className="schedule-multi-menu">
          <label className="schedule-multi-option">
            <input
              type="checkbox"
              checked={isAllSelected}
              onChange={() => toggleValue(ALL_VALUE)}
            />
            <span>{allLabel}</span>
          </label>

          {options
            .filter((option) => option !== ALL_VALUE)
            .map((option) => (
              <label key={option} className="schedule-multi-option">
                <input
                  type="checkbox"
                  checked={!isAllSelected && selected.includes(option)}
                  onChange={() => toggleValue(option)}
                />
                <span>{formatLabel(option)}</span>
              </label>
            ))}
        </div>
      )}
    </div>
  );
}

// function sessionMatchesFilters(session, filters) {
//   if (filters.lecturer !== "ALL" && session.lecturer_name !== filters.lecturer) {
//     return false;
//   }

//   if (filters.day !== "ALL" && String(session.day_of_week) !== String(filters.day)) {
//     return false;
//   }

//   const cohorts = Array.isArray(session.cohorts) ? session.cohorts : [];
//   const hasDepartmentFilter = filters.department !== "ALL";
//   const hasYearFilter = filters.yearLevel !== "ALL";

//   if (hasDepartmentFilter && hasYearFilter) {
//     return cohorts.some(
//       (cohort) =>
//         String(cohort.target_department_id) === String(filters.department) &&
//         String(cohort.target_year_level) === String(filters.yearLevel)
//     );
//   }

//   if (hasDepartmentFilter) {
//     return cohorts.some(
//       (cohort) => String(cohort.target_department_id) === String(filters.department)
//     );
//   }

//   if (hasYearFilter) {
//     return cohorts.some(
//       (cohort) => String(cohort.target_year_level) === String(filters.yearLevel)
//     );
//   }

//   return true;
// }
function sessionMatchesFilters(session, filters) {
  if (filters.lecturer !== "ALL" && session.lecturer_name !== filters.lecturer) {
    return false;
  }

  if (filters.day !== "ALL" && String(session.day_of_week) !== String(filters.day)) {
    return false;
  }

  const cohorts = Array.isArray(session.cohorts) ? session.cohorts : [];

  // if (filters.department !== "ALL") {
  //   const hasDepartment = cohorts.some(
  //     (cohort) => String(cohort.target_department_id) === String(filters.department)
  //   );
  //   if (!hasDepartment) return false;
  // }
  if (
    Array.isArray(filters.departments) &&
    !filters.departments.includes("ALL")
  ) {
    const hasDepartment = cohorts.some((cohort) =>
      filters.departments.includes(String(cohort.target_department_id))
    );

    if (!hasDepartment) return false;
  }

  if (!sessionMatchesAnyYear(session, filters.yearLevels)) return false;
  if (!sessionMatchesGroup(session, filters.groups)) return false;
  if (!sessionMatchesCourse(session, filters.course)) return false;
  if (!sessionMatchesTimeRange(session, filters.timeRange)) return false;

  return true;
}

function sessionsOverlapInTime(sessionA, sessionB) {
  if (String(sessionA.day_of_week) !== String(sessionB.day_of_week)) {
    return false;
  }

  return (
    String(sessionA.start_time).slice(0, 5) < String(sessionB.end_time).slice(0, 5) &&
    String(sessionB.start_time).slice(0, 5) < String(sessionA.end_time).slice(0, 5)
  );
}

function sessionMatchesAnyYear(session, selectedYears) {
  if (!Array.isArray(selectedYears) || selectedYears.includes("ALL")) return true;

  const cohorts = Array.isArray(session.cohorts) ? session.cohorts : [];
  return cohorts.some((cohort) =>
    selectedYears.includes(String(cohort.target_year_level))
  );
}

function sessionMatchesGroup(session, groups) {
  if (!Array.isArray(groups) || groups.includes("ALL")) return true;

  return groups.includes(String(session.group_number));
}

function sessionMatchesCourse(session, course) {
  if (!course || course === "ALL") return true;
  return String(session.course_number) === String(course);
}

function sessionMatchesTimeRange(session, timeRange) {
  if (!timeRange || timeRange === "ALL") return true;

  const startHour = Number(String(session.start_time || "").slice(0, 2));

  if (timeRange === "MORNING") return startHour >= 8 && startHour < 12;
  if (timeRange === "NOON") return startHour >= 12 && startHour < 16;
  if (timeRange === "EVENING") return startHour >= 16 && startHour <= 20;

  return true;
}

function sessionMatchesDepartmentAndYear(session, departmentId, yearLevel) {
  const cohorts = Array.isArray(session.cohorts) ? session.cohorts : [];

  return cohorts.some(
    (cohort) =>
      String(cohort.target_department_id) === String(departmentId) &&
      String(cohort.target_year_level) === String(yearLevel)
  );
}

function findDepartmentYearConflicts(sessionsList, departmentId, yearLevel) {
  const relevantSessions = (sessionsList || []).filter((session) =>
    sessionMatchesDepartmentAndYear(session, departmentId, yearLevel)
  );

  const conflicts = [];

  for (let i = 0; i < relevantSessions.length; i += 1) {
    for (let j = i + 1; j < relevantSessions.length; j += 1) {
      if (sessionsOverlapInTime(relevantSessions[i], relevantSessions[j])) {
        conflicts.push({
          firstSession: relevantSessions[i],
          secondSession: relevantSessions[j],
        });
      }
    }
  }

  return conflicts;
}

function findLecturerConflicts(sessionsList) {
  const conflicts = [];

  for (let i = 0; i < (sessionsList || []).length; i += 1) {
    for (let j = i + 1; j < (sessionsList || []).length; j += 1) {
      const firstSession = sessionsList[i];
      const secondSession = sessionsList[j];

      // Ignore duplicate representations of the same DB session.
      if (String(firstSession.session_id) === String(secondSession.session_id)) {
        continue;
      }

      const firstLecturerId = firstSession.lecturer_internal_id;
      const secondLecturerId = secondSession.lecturer_internal_id;

      if (firstLecturerId == null || secondLecturerId == null) {
        continue;
      }

      const sameLecturer =
        String(firstLecturerId) === String(secondLecturerId);

      if (!sameLecturer) continue;

      if (sessionsOverlapInTime(firstSession, secondSession)) {
        conflicts.push({
          firstSession,
          secondSession,
        });
      }
    }
  }

  return conflicts;
}

function didSessionChange(originalSession, draftSession) {
  if (!originalSession || !draftSession) return false;

  return (
    String(originalSession.day_of_week) !== String(draftSession.day_of_week) ||
    String(originalSession.start_time) !== String(draftSession.start_time) ||
    String(originalSession.end_time) !== String(draftSession.end_time)
  );
}

export default function SecretarySchedulePage() {
  const { useMock } = useMockMode();

  const [semester, setSemester] = useState(null);
  const [solverStatus, setSolverStatus] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [filters, setFilters] = useState({
    lecturer: "ALL",
    day: "ALL",
    departments: ["ALL"],
    yearLevels: ["ALL"],
    group: "ALL",
    course: "ALL",
    timeRange: "ALL",
    showMode: "ALL",
  });

  const [isLoading, setIsLoading] = useState(true);
  const [isPolling, setIsPolling] = useState(false);
  const [isRefreshingDetails, setIsRefreshingDetails] = useState(false);
  const [error, setError] = useState("");

  const [isGenerating, setIsGenerating] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const [isEditMode, setIsEditMode] = useState(false);
  const [draftSessions, setDraftSessions] = useState([]);
  const [originalSessions, setOriginalSessions] = useState([]);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  const [editConfirmOpen, setEditConfirmOpen] = useState(false);
  const [editConfirmAction, setEditConfirmAction] = useState(null);
  const [isSavingEdits, setIsSavingEdits] = useState(false);

  const scheduleId = useMemo(() => solverStatus?.schedule_id || null, [solverStatus]);

  const lecturerOptions = useMemo(() => {
    const uniqueLecturers = new Set(
      (sessions || []).map((session) => session.lecturer_name).filter(Boolean)
    );

    return ["ALL", ...Array.from(uniqueLecturers).sort((a, b) => a.localeCompare(b))];
  }, [sessions]);

  const groupOptions = useMemo(() => {
    const groups = new Set();

    (sessions || []).forEach((session) => {
      if (session.group_number != null) groups.add(String(session.group_number));
    });

    return ["ALL", ...Array.from(groups).sort((a, b) => Number(a) - Number(b))];
  }, [sessions]);

  const courseOptions = useMemo(() => {
    const courses = new Map();

    (sessions || []).forEach((session) => {
      if (session.course_number != null) {
        courses.set(
          String(session.course_number),
          `${session.course_name} (${session.course_number})`
        );
      }
    });

    return [
      { value: "ALL", label: "All Courses" },
      ...Array.from(courses.entries()).map(([value, label]) => ({ value, label })),
    ];
  }, [sessions]);

  const departmentOptions = useMemo(() => {
    const ids = new Set();

    (sessions || []).forEach((session) => {
      const cohorts = Array.isArray(session.cohorts) ? session.cohorts : [];
      cohorts.forEach((cohort) => {
        if (cohort?.target_department_id != null) {
          ids.add(String(cohort.target_department_id));
        }
      });
    });

    return ["ALL", ...Array.from(ids).sort((a, b) => Number(a) - Number(b))];
  }, [sessions]);

  const yearLevelOptions = useMemo(() => {
    const levels = new Set();

    (sessions || []).forEach((session) => {
      const cohorts = Array.isArray(session.cohorts) ? session.cohorts : [];
      cohorts.forEach((cohort) => {
        if (cohort?.target_year_level != null) {
          levels.add(String(cohort.target_year_level));
        }
      });
    });

    return ["ALL", ...Array.from(levels).sort((a, b) => Number(a) - Number(b))];
  }, [sessions]);

  // const isViewFilterReady = useMemo(() => {
  //   const hasLecturer = filters.lecturer !== "ALL";
  //   const hasDepartmentAndYear =
  //     filters.department !== "ALL" && filters.yearLevel !== "ALL";

  //   return hasLecturer || hasDepartmentAndYear;
  // }, [filters]);
  const isViewFilterReady = useMemo(() => {
    return (
      filters.lecturer !== "ALL" ||
      !filters.departments.includes("ALL") ||
      !filters.yearLevels.includes("ALL") ||
      filters.groups !== "ALL" ||
      filters.course !== "ALL"
    );
  }, [filters]);

  // const isEditFilterReady = useMemo(() => {
  //   return filters.department !== "ALL" && filters.yearLevel !== "ALL";
  // }, [filters]);
  const isEditFilterReady = useMemo(() => {
    return (
      Array.isArray(filters.departments) &&
      filters.departments.length === 1 &&
      !filters.departments.includes("ALL") &&
      Array.isArray(filters.yearLevels) &&
      filters.yearLevels.length === 1 &&
      !filters.yearLevels.includes("ALL")
    );
  }, [filters]);

  const filteredSessions = useMemo(() => {
    return (sessions || []).filter((session) => sessionMatchesFilters(session, filters));
  }, [sessions, filters]);

  const filteredDraftSessions = useMemo(() => {
    return (draftSessions || []).filter((session) => sessionMatchesFilters(session, filters));
  }, [draftSessions, filters]);

  const sessionsForGrid = isEditMode ? filteredDraftSessions : filteredSessions;

  // const draftDepartmentYearConflicts = useMemo(() => {
  //   if (filters.department === "ALL" || filters.yearLevel === "ALL") {
  //     return [];
  //   }

  //   return findDepartmentYearConflicts(
  //     draftSessions,
  //     filters.department,
  //     filters.yearLevel
  //   );
  // }, [draftSessions, filters.department, filters.yearLevel]);
  const draftDepartmentYearConflicts = useMemo(() => {
    if (!isEditFilterReady) return [];

    return findDepartmentYearConflicts(
      draftSessions,
      filters.departments[0],
      filters.yearLevels[0]
    );
  }, [draftSessions, filters.departments, filters.yearLevels, isEditFilterReady]);

  const draftLecturerConflicts = useMemo(() => {
    return findLecturerConflicts(draftSessions);
  }, [draftSessions]);

  useEffect(() => {
    if (!isEditMode) return;

    if (
      draftDepartmentYearConflicts.length === 0 &&
      draftLecturerConflicts.length === 0
    ) {
      setError("");
    }
  }, [isEditMode, draftDepartmentYearConflicts, draftLecturerConflicts]);

  const fetchSolverStatus = useCallback(async (year, number) => {
    if (useMock) {
      return await mockGetSolverStatus(year, number);
    }

    const token = getToken();
    const url = `${API_BASE}/dashboard/solver_status?semester_year=${year}&semester_number=${number}`;

    const response = await fetch(url, {
      method: "GET",
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new Error(data?.detail || "Failed to load solver status");
    }

    return await response.json();
  }, [useMock]);

  const fetchScheduleDetails = useCallback(async (id) => {
    if (useMock) {
      return await mockGetScheduleDetails(id);
    }

    const response = await fetch(`${API_BASE}/schedules/${id}/details`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });

    if (!response.ok) {
      throw new Error("Failed to load schedule details");
    }

    return await response.json();
  }, [useMock]);

  useEffect(() => {
    async function boot() {
      setIsLoading(true);
      setError("");
      setSolverStatus(null);
      setSessions([]);
      setIsPolling(false);

      try {
        if (useMock) {
          const nextSemester = await mockGetSemesterInfo();
          setSemester(nextSemester);
        } else {
          const response = await fetch(
            `${API_BASE_URL}${SECRETARY_PREFIX}/dashboard/semester_info`,
            {
              headers: { Authorization: `Bearer ${getToken()}` },
            }
          );

          const data = await response.json();
          if (data?.semester_year) {
            setSemester(data);
          }
        }
      } catch (e) {
        setError(e.message);
      } finally {
        setIsLoading(false);
      }
    }

    boot();
  }, [useMock]);

  useEffect(() => {
    if (!semester) return;
    let alive = true;

    async function check() {
      try {
        setError("");

        const statusData = await fetchSolverStatus(
          semester.semester_year,
          semester.semester_number
        );

        if (!alive) return;
        setSolverStatus(statusData);

        if (statusData?.status === "solved" && statusData.schedule_id) {
          const details = await fetchScheduleDetails(statusData.schedule_id);
          if (alive) {
            setSessions(Array.isArray(details) ? details : []);
          }
        } else if (alive) {
          setSessions([]);
        }

        if (statusData?.status === "pending") {
          setIsPolling(true);
        }
      } catch (e) {
        setError(e.message);
      }
    }

    check();

    return () => {
      alive = false;
    };
  }, [semester, fetchSolverStatus, fetchScheduleDetails]);

  useEffect(() => {
    if (!semester || !isPolling) return;

    const intervalId = setInterval(async () => {
      try {
        const nextStatus = await fetchSolverStatus(
          semester.semester_year,
          semester.semester_number
        );

        setSolverStatus(nextStatus);

        if (nextStatus?.status !== "pending") {
          setIsPolling(false);

          if (nextStatus?.status === "solved") {
            const details = await fetchScheduleDetails(nextStatus.schedule_id);
            setSessions(Array.isArray(details) ? details : []);
          }
        }
      } catch (e) {
        setError(e.message);
        setIsPolling(false);
      }
    }, POLL_INTERVAL_MS);

    return () => clearInterval(intervalId);
  }, [isPolling, semester, fetchSolverStatus, fetchScheduleDetails]);

  const handleRefreshDetails = async () => {
    if (!scheduleId) return;

    setIsRefreshingDetails(true);

    try {
      const details = await fetchScheduleDetails(scheduleId);
      setSessions(Array.isArray(details) ? details : []);
    } catch (e) {
      setError(e.message);
    } finally {
      setIsRefreshingDetails(false);
    }
  };

  const handleGenerateSchedule = async () => {
    if (!semester || solverStatus?.status === "pending") return;

    setIsGenerating(true);
    setError("");

    try {
      if (useMock) {
        setSolverStatus((prev) => ({ ...(prev || {}), status: "pending" }));
        setConfirmOpen(false);
        setIsPolling(true);
        return;
      }

      const response = await fetch(`${API_BASE}/schedules/publish_request`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${getToken()}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          semester_year: semester.semester_year,
          semester_number: semester.semester_number,
          is_draft: true,
        }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        throw new Error(data?.detail || "Failed to start schedule generation");
      }

      setConfirmOpen(false);

      const nextStatus = await fetchSolverStatus(
        semester.semester_year,
        semester.semester_number
      );

      setSolverStatus(nextStatus);

      if (nextStatus?.status === "pending") {
        setIsPolling(true);
      }
    } catch (e) {
      setError(e.message || "Failed to start schedule generation");
    } finally {
      setIsGenerating(false);
    }
  };

  const saveEditedSchedule = async () => {
    if (!scheduleId) return;

    if (useMock) {
      setSessions(draftSessions);
      setHasUnsavedChanges(false);
      setIsEditMode(false);
      return;
    }

    setIsSavingEdits(true);
    setError("");

    try {
      const originalById = new Map(
        (originalSessions || []).map((session) => [String(session.session_id), session])
      );

      const changedSessions = (draftSessions || []).filter((draftSession) => {
        const originalSession = originalById.get(String(draftSession.session_id));
        return didSessionChange(originalSession, draftSession);
      });

      for (const session of changedSessions) {
        if (session.lecturer_internal_id == null) {
          throw new Error(
            "Cannot save manual schedule changes: missing lecturer identifier for one or more sessions."
          );
        }

        const startTimePayload =
          String(session.start_time).length === 5
            ? `${session.start_time}:00`
            : session.start_time;
        const endTimePayload =
          String(session.end_time).length === 5
            ? `${session.end_time}:00`
            : session.end_time;

        const normalizedEnd = String(endTimePayload).slice(0, 5);
        const dayNumber = Number(session.day_of_week);

        if (dayNumber === 6 && normalizedEnd > "14:00") {
          throw new Error("Cannot save schedule: Friday sessions must end by 14:00.");
        }

        if (dayNumber >= 1 && dayNumber <= 5 && normalizedEnd > "20:00") {
          throw new Error(
            "Cannot save schedule: Sunday-Thursday sessions must end by 20:00."
          );
        }

        const payload = {
          offering_id: session.offering_id,
          lecturer_internal_id: session.lecturer_internal_id,
          day_of_week: session.day_of_week,
          start_time: startTimePayload,
          end_time: endTimePayload,
        };

        const response = await fetch(`${API_BASE}/schedules/${scheduleId}/sessions`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${getToken()}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        });

        if (!response.ok) {
          const data = await response.json().catch(() => null);
          throw new Error(data?.detail || "Failed to save manual schedule changes");
        }
      }

      const refreshedDetails = await fetchScheduleDetails(scheduleId);
      const normalizedDetails = Array.isArray(refreshedDetails) ? refreshedDetails : [];

      setSessions(normalizedDetails);
      setDraftSessions(normalizedDetails);
      setOriginalSessions(normalizedDetails);
      setHasUnsavedChanges(false);
      setIsEditMode(false);
      setEditConfirmOpen(false);
      setEditConfirmAction(null);
    } catch (e) {
      setError(e.message || "Failed to save manual schedule changes");
    } finally {
      setIsSavingEdits(false);
    }
  };

  const enterEditMode = () => {
    setOriginalSessions(sessions);
    setDraftSessions(sessions);
    setHasUnsavedChanges(false);
    setError("");
    setIsEditMode(true);
  };

  const askToSaveEditChanges = () => {
    if (!hasUnsavedChanges) {
      setIsEditMode(false);
      return;
    }

    if (draftDepartmentYearConflicts.length > 0) {
      setError(
        "Cannot save schedule: this department and year contain overlapping sessions."
      );
      return;
    }

    if (draftLecturerConflicts.length > 0) {
      setError(
        "Cannot save schedule: one or more lecturers are assigned to overlapping sessions."
      );
      return;
    }

    setEditConfirmAction("save");
    setEditConfirmOpen(true);
  };

  const cancelEditMode = () => {
    if (hasUnsavedChanges) {
      setEditConfirmAction("discard");
      setEditConfirmOpen(true);
      return;
    }

    setDraftSessions(originalSessions);
    setIsEditMode(false);
  };

  const handleEditConfirm = async () => {
    if (editConfirmAction === "save") {
      await saveEditedSchedule();
      return;
    }

    if (editConfirmAction === "discard") {
      setDraftSessions(originalSessions);
      setHasUnsavedChanges(false);
      setIsEditMode(false);
    }

    setEditConfirmOpen(false);
    setEditConfirmAction(null);
  };

  const renderSolverBlock = () => {
    if (!solverStatus && !error) {
      return (
        <div className="solver-pill">
          <div className="mini-spinner" />
          <span>Loading solver status...</span>
        </div>
      );
    }

    if (error) {
      return (
        <div className="solver-pill solver-pill-error">
          <span>{error}</span>
        </div>
      );
    }

    if (!solverStatus) return null;

    if (solverStatus.status === "pending") {
      return (
        <div className="solver-status-area">
          <div className="solver-pill pending">
            <div className="mini-spinner" /> Generating...
          </div>
        </div>
      );
    }

    if (solverStatus.status === "solved") {
      return (
        <div className="solver-status-area">
          <div className="solver-pill solved">✓ Ready (ID: {scheduleId})</div>
        </div>
      );
    }

    if (solverStatus.status === "failed") {
      return (
        <div className="solver-status-area">
          <div className="solver-pill error">✕ Failed</div>
        </div>
      );
    }

    return null;
  };

  return (
    <div className="schedule-page secretary-schedule-page">
      <div className="schedule-inner">
        <header className="schedule-header">
          <div>
            <h1 className="schedule-title">Schedule Overview</h1>
            <p className="schedule-subtitle">
              {semester
                ? `${SEMESTER_LABELS[semester.semester_number]} ${semester.semester_year}`
                : "Loading..."}
            </p>
          </div>

          <div className="schedule-header-actions">
            <button
              className="button button-primary"
              disabled={!semester || solverStatus?.status === "pending" || isGenerating}
              onClick={() => {
                if (solverStatus?.status === "solved") {
                  setConfirmOpen(true);
                } else {
                  handleGenerateSchedule();
                }
              }}
            >
              {solverStatus?.status === "pending"
                ? "Generating..."
                : isGenerating
                  ? "Starting..."
                  : solverStatus?.status === "solved"
                    ? "Re-Generate"
                    : "Generate"}
            </button>

            <button
              className="button button-secondary"
              onClick={handleRefreshDetails}
              disabled={!scheduleId || isRefreshingDetails}
            >
              {isRefreshingDetails ? "Refreshing..." : "Refresh Grid"}
            </button>

            {!isEditMode && solverStatus?.status === "solved" && (
              <button
                className="button button-secondary"
                onClick={enterEditMode}
                disabled={!isEditFilterReady}
              >
                Edit Schedule
              </button>
            )}

            {isEditMode && (
              <>
                <button className="button button-secondary" onClick={cancelEditMode}>
                  Cancel
                </button>

                <button className="button button-primary" onClick={askToSaveEditChanges}>
                  Finish
                </button>
              </>
            )}
          </div>
        </header>


        {/* <div className="schedule-toolbar">
          {renderSolverBlock()}

          <div className="filters-bar">
            <div className="filter-field">
              <label>Lecturer</label>
              <select
                value={filters.lecturer}
                onChange={(e) =>
                  setFilters((prev) => ({ ...prev, lecturer: e.target.value }))
                }
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
                onChange={(e) =>
                  setFilters((prev) => ({ ...prev, day: e.target.value }))
                }
              >
                {DAY_OPTIONS.map((day) => (
                  <option key={day.value} value={day.value}>
                    {day.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="filter-field">
              <label>Department</label>
              <select
                value={filters.department}
                onChange={(e) =>
                  setFilters((prev) => ({ ...prev, department: e.target.value }))
                }
                disabled={departmentOptions.length <= 1}
              >
                {departmentOptions.map((id) => (
                  <option key={id} value={id}>
                    {id === "ALL" ? "All departments" : id}
                  </option>
                ))}
              </select>
            </div>

            <div className="filter-field">
              <label>Year</label>
              <select
                value={filters.yearLevel}
                onChange={(e) =>
                  setFilters((prev) => ({ ...prev, yearLevel: e.target.value }))
                }
                disabled={yearLevelOptions.length <= 1}
              >
                {yearLevelOptions.map((year) => (
                  <option key={year} value={year}>
                    {year === "ALL" ? "All years" : `Year ${year}`}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div> */}
        <div className="schedule-toolbar schedule-toolbar-modern">
          <div className="schedule-filter-panel">
            <div className="schedule-filter-top">
              {renderSolverBlock()}

              <button type="button" className="schedule-filter-toggle">
                Filters
              </button>
            </div>

            <div className="schedule-filter-grid">
              <div className="filter-field">
                <label>Lecturer</label>
                <select
                  value={filters.lecturer}
                  onChange={(e) =>
                    setFilters((prev) => ({ ...prev, lecturer: e.target.value }))
                  }
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
                  onChange={(e) =>
                    setFilters((prev) => ({ ...prev, day: e.target.value }))
                  }
                >
                  {DAY_OPTIONS.map((day) => (
                    <option key={day.value} value={day.value}>
                      {day.label}
                    </option>
                  ))}
                </select>
              </div>

              {/* <div className="filter-field">
                <label>Department</label>
                <select
                  value={filters.department}
                  onChange={(e) =>
                    setFilters((prev) => ({ ...prev, department: e.target.value }))
                  }
                  disabled={departmentOptions.length <= 1}
                >
                  {departmentOptions.map((id) => (
                    <option key={id} value={id}>
                      {id === "ALL" ? "All departments" : id}
                    </option>
                  ))}
                </select>
              </div> */}
              <MultiSelectDropdown
                label="Department"
                options={departmentOptions}
                selectedValues={filters.departments}
                allLabel="All departments"
                formatLabel={(id) => `Department ${id}`}
                disabled={departmentOptions.length <= 1}
                onChange={(next) =>
                  setFilters((prev) => ({ ...prev, departments: next }))
                }
              />

              {/* <div className="filter-field">
                <label>Year(s)</label>
                <select
                  multiple
                  className="schedule-years-multiselect"
                  value={filters.yearLevels}
                  onChange={(e) => {
                    const selected = Array.from(e.target.selectedOptions).map(
                      (option) => option.value
                    );

                    setFilters((prev) => ({
                      ...prev,
                      yearLevels:
                        selected.includes("ALL") || selected.length === 0
                          ? ["ALL"]
                          : selected,
                    }));
                  }}
                  disabled={yearLevelOptions.length <= 1}
                >
                  {yearLevelOptions.map((year) => (
                    <option key={year} value={year}>
                      {year === "ALL" ? "All Years" : `Year ${year}`}
                    </option>
                  ))}
                </select>
              </div> */}
              <MultiSelectDropdown
                label="Year(s)"
                options={yearLevelOptions}
                selectedValues={filters.yearLevels}
                allLabel="All Years"
                formatLabel={(year) => `Year ${year}`}
                disabled={yearLevelOptions.length <= 1}
                onChange={(next) =>
                  setFilters((prev) => ({ ...prev, yearLevels: next }))
                }
              />

              {/* <div className="filter-field">
                <label>Groups</label>
                <select
                  value={filters.group}
                  onChange={(e) =>
                    setFilters((prev) => ({ ...prev, group: e.target.value }))
                  }
                  disabled={groupOptions.length <= 1}
                >
                  {groupOptions.map((group) => (
                    <option key={group} value={group}>
                      {group === "ALL" ? "All Groups" : `Group ${group}`}
                    </option>
                  ))}
                </select>
              </div> */}
              <MultiSelectDropdown
                label="Groups"
                options={groupOptions}
                selectedValues={
                  Array.isArray(filters.groups)
                    ? filters.groups
                    : ["ALL"]
                }
                allLabel="All Groups"
                formatLabel={(group) => `Group ${group}`}
                disabled={groupOptions.length <= 1}
                onChange={(next) =>
                  setFilters((prev) => ({
                    ...prev,
                    groups: next,
                  }))
                }
              />

              <div className="filter-field">
                <label>Course</label>
                <select
                  value={filters.course}
                  onChange={(e) =>
                    setFilters((prev) => ({ ...prev, course: e.target.value }))
                  }
                  disabled={courseOptions.length <= 1}
                >
                  {courseOptions.map((course) => (
                    <option key={course.value} value={course.value}>
                      {course.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="filter-field">
                <label>Time range</label>
                <select
                  value={filters.timeRange}
                  onChange={(e) =>
                    setFilters((prev) => ({ ...prev, timeRange: e.target.value }))
                  }
                >
                  <option value="ALL">08:00 - 20:00</option>
                  <option value="MORNING">Morning: 08:00 - 12:00</option>
                  <option value="NOON">Noon: 12:00 - 16:00</option>
                  <option value="EVENING">Evening: 16:00 - 20:00</option>
                </select>
              </div>
            </div>

            <button
              type="button"
              className="schedule-clear-filters"
              onClick={() =>
                setFilters({
                  lecturer: "ALL",
                  day: "ALL",
                  departments: ["ALL"],
                  yearLevels: ["ALL"],
                  group: ["ALL"],
                  course: "ALL",
                  timeRange: "ALL",
                  showMode: "ALL",
                })
              }
            >
              Clear all filters
            </button>
          </div>
        </div>

        {isLoading ? (
          <div className="spinner" />
        ) : (
          <>
            {solverStatus?.status === "failed" &&
              solverStatus.broken_constraint_details && (
                <div className="card conflicts-card">
                  <h3>Conflicts Found</h3>
                  <ul className="conflicts-list">
                    {solverStatus.broken_constraint_details.map((conflict, index) => (
                      <li key={index}>
                        <strong>{conflict.lecturer_name}:</strong> {conflict.raw_text}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

            {solverStatus?.status === "none" && <NoScheduleState />}

            {solverStatus?.status === "solved" &&
              sessions.length > 0 &&
              !isViewFilterReady && (
                <div className="schedule-empty-screen schedule-empty-hint">
                  <h3>Choose a lecturer, or choose both Department and Year</h3>
                </div>
              )}

            {solverStatus?.status === "solved" &&
              sessions.length > 0 &&
              isViewFilterReady &&
              (sessionsForGrid.length > 0 ? (
                isEditMode ? (
                  <EditableWeeklyScheduleGrid
                    sessions={sessionsForGrid}
                    showLecturer
                    setDraftSessions={setDraftSessions}
                    setHasUnsavedChanges={setHasUnsavedChanges}
                  />
                ) : (
                  <WeeklyScheduleGrid sessions={sessionsForGrid} showLecturer />
                )
              ) : (
                <div className="schedule-empty-screen schedule-empty-hint schedule-empty-hint--small">
                  <h3>No sessions match the current filters</h3>
                </div>
              ))}
          </>
        )}
      </div>

      <ConfirmModal
        open={confirmOpen}
        title="Re-generate schedule?"
        message="Are you sure you want to regenerate? This will start the solver and may produce a different schedule."
        confirmText="Yes, regenerate"
        cancelText="Cancel"
        loading={isGenerating}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => {
          setConfirmOpen(false);
          handleGenerateSchedule();
        }}
      />

      <ConfirmModal
        open={editConfirmOpen}
        title={editConfirmAction === "save" ? "Save changes?" : "Discard changes?"}
        message={
          editConfirmAction === "save"
            ? "Are you sure you want to save your manual changes?"
            : "Are you sure you want to discard your changes?"
        }
        confirmText={editConfirmAction === "save" ? "Save" : "Discard"}
        cancelText="Cancel"
        loading={isSavingEdits}
        onCancel={() => {
          setEditConfirmOpen(false);
          setEditConfirmAction(null);
        }}
        onConfirm={handleEditConfirm}
      />
    </div>
  );
}