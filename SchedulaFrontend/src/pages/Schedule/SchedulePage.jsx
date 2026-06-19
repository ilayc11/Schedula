// src/pages/Schedule/SchedulePage.jsx
import { useEffect, useMemo, useState, useCallback } from "react";
import "./SchedulePage.css";

import NoScheduleState from "../../components/NoScheduleState";
import WeeklyScheduleGrid from "../../components/WeeklyScheduleGrid";
import { useMockMode } from "../../context/MockModeContext.jsx";
import ConfirmModal from "../../components/ConfirmModal.jsx";
import { useNavigate } from "react-router-dom";


const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const LECTURER_PREFIX = import.meta.env.VITE_API_PREFIX_LECTURER || "/lecturer";
const API_BASE = API_BASE_URL + LECTURER_PREFIX;

/* MOCK CONFIG */
const MOCK_CURRENT_SEMESTER = {
  semester_year: 2026,
  semester_number: 1,
  status: "CHA", // SET | SUB | REV | CHA | PUB
};

const MOCK_SESSIONS = [
  {
    session_id: 1,
    schedule_id: 12,
    day_of_week: 1,
    start_time: "10:00",
    end_time: "12:00",
    course_name: "Algorithms",
    course_number: 20417,
    offering_id: 50,
    group_number: 1,
    lecturer_name: "You",
    semester_year: 2026,
    semester_number: 1,
  },
  {
    session_id: 2,
    schedule_id: 12,
    day_of_week: 3,
    start_time: "13:00",
    end_time: "14:00",
    course_name: "Databases",
    course_number: 20277,
    offering_id: 51,
    group_number: 2,
    lecturer_name: "You",
    semester_year: 2026,
    semester_number: 1,
  },
  {
    session_id: 3,
    schedule_id: 12,
    day_of_week: 4,
    start_time: "17:00",
    end_time: "20:00",
    course_name: "Web Dev",
    course_number: 37210,
    offering_id: 52,
    group_number: 1,
    lecturer_name: "You",
    semester_year: 2026,
    semester_number: 1,
  },
];

function readCurrentSemesterFromStorage() {
  try {
    const raw = localStorage.getItem("current_semester");
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function writeCurrentSemesterToStorage(sem) {
  try {
    localStorage.setItem(
      "current_semester",
      JSON.stringify({
        semester_year: sem?.semester_year,
        semester_number: sem?.semester_number,
        status: sem?.status,
        updated_at: new Date().toISOString(),
      })
    );
  } catch {}
}
function approvalStorageKey(semester_year, semester_number, schedule_id) {
  const y = semester_year ?? "na";
  const n = semester_number ?? "na";
  const s = schedule_id ?? "na";
  return `schedule_approval_${y}_${n}_${s}`;
}

function readMockApproval(semester_year, semester_number, schedule_id) {
  try {
    const key = approvalStorageKey(semester_year, semester_number, schedule_id);
    const raw = localStorage.getItem(key);
    const data = raw ? JSON.parse(raw) : null;
    return data?.status || "PEN";
  } catch {
    return "PEN";
  }
}

function writeMockApproval(semester_year, semester_number, schedule_id, status) {
  try {
    const key = approvalStorageKey(semester_year, semester_number, schedule_id);
    localStorage.setItem(key, JSON.stringify({ status, at: new Date().toISOString() }));
  } catch {}
}

function SchedulePage() {
  const { useMock } = useMockMode();

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  const [semester, setSemester] = useState(null);
  const [sessions, setSessions] = useState([]);
  // const [semesterStatus, setSemesterStatus] = useState(null);
  // const [isSubmissionPeriod, setIsSubmissionPeriod] = useState(false);

  const [semesterStatus, setSemesterStatus] = useState(null);
  const [approvalStatus, setApprovalStatus] = useState("PEN"); // APP | REJ | PEN

  const [approveOpen, setApproveOpen] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [isFeedbackSubmitting, setIsFeedbackSubmitting] = useState(false);

  const scheduleId = useMemo(() => {
    const first = Array.isArray(sessions) ? sessions[0] : null;
    return first?.schedule_id ?? null;
  }, [sessions]);

  const navigate = useNavigate();

  const hasSchedule = useMemo(() => Array.isArray(sessions) && sessions.length > 0, [sessions]);

  const refreshSemesterStatusFromStorage = useCallback(() => {
    const stored = readCurrentSemesterFromStorage();
    setSemesterStatus(stored?.status ?? null);
  }, []);

  const isPublished = useMemo(() => semesterStatus === "CHA" || semesterStatus === "PUB", [semesterStatus]);
  const canShowTemporary = isPublished && semesterStatus === "CHA";
  const canShowFinal = isPublished && semesterStatus === "PUB";

  const loadApprovalStatus = useCallback(
    async (semester_year, semester_number, schedule_id) => {
      if (!schedule_id) {
        setApprovalStatus("PEN");
        return;
      }

      if (useMock) {
        setApprovalStatus(readMockApproval(semester_year, semester_number, schedule_id));
        return;
      }

      try {
        const token = localStorage.getItem("access_token");
        if (!token) {
          setApprovalStatus("PEN");
          return;
        }

        const res = await fetch(`${API_BASE}/schedules/approval/${schedule_id}`, {
          method: "GET",
          headers: { Authorization: `Bearer ${token}` },
        });

        // backend might return 404 if no approval exists yet
        if (!res.ok) {
          setApprovalStatus("PEN");
          return;
        }

        const data = await res.json().catch(() => null);
        const status = data?.status ?? data?.data?.status ?? "PEN";
        setApprovalStatus(status);
      } catch {
        setApprovalStatus("PEN");
      }
    },
    [useMock]
  );


  const load = useCallback(async () => {
    setIsLoading(true);
    setError("");
    refreshSemesterStatusFromStorage();

// <<<<<<< breaking-constraint-sec
//     refreshSemesterStatusFromStorage();
// =======
//         if (!alive) return;
//         setSemester(currentSemester);
//         setSemesterStatus(semData.status);

//         // If semester is in constraint submission period (SUB), skip schedule fetch
//         if (semData.status === "SUB") {
//           setIsSubmissionPeriod(true);
//           setSessions([]);
//           setIsLoading(false);
//           return;
//         }
// >>>>>>> main

    try {
      const token = localStorage.getItem("access_token");

      if (useMock) {
        await new Promise((resolve) => setTimeout(resolve, 500));

        setSemester({
          semester_year: MOCK_CURRENT_SEMESTER.semester_year,
          semester_number: MOCK_CURRENT_SEMESTER.semester_number,
        });

//         // Always keep sessions available, but UI will decide if to show them
        setSessions(MOCK_SESSIONS);

        writeCurrentSemesterToStorage(MOCK_CURRENT_SEMESTER);
        setSemesterStatus(MOCK_CURRENT_SEMESTER.status);
        const sid = MOCK_SESSIONS[0]?.schedule_id ?? null;
        await loadApprovalStatus(
          MOCK_CURRENT_SEMESTER.semester_year,
          MOCK_CURRENT_SEMESTER.semester_number,
          sid
        );

        return;
      }
// =======
//         if (!schRes.ok) {
//           const schData = await schRes.json().catch(() => null);
//           // Check for specific error code indicating submission period
//           if (schData?.detail === "SCHEDULE_HIDDEN_DURING_SUBMISSION") {
//             if (!alive) return;
//             setIsSubmissionPeriod(true);
//             setSessions([]);
//             setIsLoading(false);
//             return;
//           }
//           throw new Error(schData?.detail || "Failed to load schedule");
//         }
// >>>>>>> main

      if (!token) throw new Error("Missing access token");

      const semRes = await fetch(`${API_BASE}/dashboard/current_semester`, {
        method: "GET",
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!semRes.ok) {
        const semDataErr = await semRes.json().catch(() => null);
        throw new Error(semDataErr?.detail || "Failed to load current semester");
      }

      const semData = await semRes.json();

      if (!semData?.semester_year || !semData?.semester_number) {
        setSemester(null);
        setSessions([]);
        setSemesterStatus(null);
        return;
      }

      const currentSemester = {
        semester_year: semData.semester_year,
        semester_number: semData.semester_number,
      };

      setSemester(currentSemester);

      if (semData?.status) {
        writeCurrentSemesterToStorage({
          semester_year: semData.semester_year,
          semester_number: semData.semester_number,
          status: semData.status,
        });
        setSemesterStatus(semData.status);
      } else {
        refreshSemesterStatusFromStorage();
      }

      const url =
        `${API_BASE}/schedules/my_schedule` +
        `?semester_year=${currentSemester.semester_year}` +
        `&semester_number=${currentSemester.semester_number}`;

      const schRes = await fetch(url, {
        method: "GET",
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!schRes.ok) {
        const schDataErr = await schRes.json().catch(() => null);
        throw new Error(schDataErr?.detail || "Failed to load schedule");
      }

      // const schData = await schRes.json();
      // setSessions(Array.isArray(schData) ? schData : []);
      const schData = await schRes.json();
      const list = Array.isArray(schData) ? schData : [];
      setSessions(list);

      const sid = list[0]?.schedule_id ?? null;
      await loadApprovalStatus(currentSemester.semester_year, currentSemester.semester_number, sid);

    } catch (e) {
      setError(e?.message || "Unexpected error while loading schedule");
    } finally {
      setIsLoading(false);
    }
  }, [useMock, refreshSemesterStatusFromStorage, loadApprovalStatus]);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      await load();
      if (cancelled) return;
    })();

    return () => {
      cancelled = true;
    };
  }, [load]);

  // const submitFeedbackLocal = useCallback(async (decision) => {
  //   try {
  //     const key = "schedule_feedback";
  //     localStorage.setItem(key, JSON.stringify({ decision, at: new Date().toISOString() }));
  //   } catch {}
  // }, []);

  const handleApprove = useCallback(async () => {
    setIsFeedbackSubmitting(true);
    setError("");

    try {
      await new Promise((resolve) => setTimeout(resolve, useMock ? 400 : 150));

      if (useMock) {
        // await submitFeedbackLocal("APPROVE");
        // setApproveOpen(false);
        // return;
        const semYear = semester?.semester_year ?? MOCK_CURRENT_SEMESTER.semester_year;
        const semNum = semester?.semester_number ?? MOCK_CURRENT_SEMESTER.semester_number;
        const sid = scheduleId ?? MOCK_SESSIONS[0]?.schedule_id ?? null;

        writeMockApproval(semYear, semNum, sid, "APP");
        setApprovalStatus("APP");
        setApproveOpen(false);
        return;
      }

      const token = localStorage.getItem("access_token");
      if (!token) throw new Error("Missing access token");
      if (!scheduleId) throw new Error("Missing schedule id");

      const res = await fetch(`${API_BASE}/schedules/approval`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          schedule_id: scheduleId,
          status: "APP",
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || `Error ${res.status}`);
      }

      setApproveOpen(false);
      setApprovalStatus("APP");

    } catch (e) {
      setError(e?.message || "Failed to submit approval");
    } finally {
      setIsFeedbackSubmitting(false);
    }
  // }, [useMock, submitFeedbackLocal, scheduleId]);
  }, [useMock, scheduleId, semester]);


  const handleReject = useCallback(async () => {
    setIsFeedbackSubmitting(true);
    setError("");

    try {
      await new Promise((resolve) => setTimeout(resolve, useMock ? 400 : 150));

      if (useMock) {
        // await submitFeedbackLocal("REJECT");
        // setRejectOpen(false);
        // navigate("/lecturer/constraints/write");
        // return;
        const semYear = semester?.semester_year ?? MOCK_CURRENT_SEMESTER.semester_year;
        const semNum = semester?.semester_number ?? MOCK_CURRENT_SEMESTER.semester_number;
        const sid = scheduleId ?? MOCK_SESSIONS[0]?.schedule_id ?? null;

        writeMockApproval(semYear, semNum, sid, "REJ");
        setApprovalStatus("REJ");
        setRejectOpen(false);
        navigate("/lecturer/constraints/write");
        return;
      }

      const token = localStorage.getItem("access_token");
      if (!token) throw new Error("Missing access token");
      if (!scheduleId) throw new Error("Missing schedule id");

      const res = await fetch(`${API_BASE}/schedules/approval`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          schedule_id: scheduleId,
          status: "REJ",
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || `Error ${res.status}`);
      }

      setApprovalStatus("REJ");
      setRejectOpen(false);
      navigate("/lecturer/constraints/write");
    } catch (e) {
      setError(e?.message || "Failed to submit rejection");
    } finally {
      setIsFeedbackSubmitting(false);
    }
  // }, [useMock, submitFeedbackLocal, scheduleId, navigate]);
  }, [useMock, scheduleId, semester, navigate]);

  return (
    <div className="schedule-page">
      <div className="schedule-inner">
        <header className="schedule-header">
          <div>
            <h1 className="schedule-title">My Schedule</h1>
            <p className="schedule-subtitle">
              {semester
                ? `Semester: ${semester.semester_number} / ${semester.semester_year}`
                : "Semester information is not available"}
            </p>
          </div>
        </header>

        {/* TEMPORARY: only if published and status=CHA */}
        {/* {!isLoading && !error && hasSchedule && canShowTemporary && ( */}
        {!isLoading && !error && hasSchedule && canShowTemporary && approvalStatus === "PEN" && (
          <div className="schedule-banner schedule-banner-temporary">
            <div className="schedule-banner-title">Temporary schedule</div>
            <div className="schedule-banner-text">
              This schedule is temporary and may change during the changes period.
            </div>

            <div className="schedule-banner-actions">
              <button
                type="button"
                className="button button-primary"
                onClick={() => setApproveOpen(true)}
                disabled={isFeedbackSubmitting}
              >
                Approve
              </button>
              <button
                type="button"
                className="button button-secondary"
                onClick={() => setRejectOpen(true)}
                disabled={isFeedbackSubmitting}
              >
                Reject
              </button>
            </div>
          </div>
        )}
        {!isLoading && !error && hasSchedule && canShowTemporary && approvalStatus === "APP" && (
          <div className="schedule-banner schedule-banner-final">
            <div className="schedule-banner-title">Thanks, you approved</div>
            <div className="schedule-banner-text">We will notify you when the final schedule is published.</div>
          </div>
        )}


        {/* FINAL: only if published and status=PUB */}
        {!isLoading && !error && hasSchedule && canShowFinal && (
          <div className="schedule-banner schedule-banner-final">
            <div className="schedule-banner-title">Final schedule</div>
          </div>
        )}

        {/* Loading */}
        {isLoading && (
          <div className="schedule-loading">
            <div className="spinner" />
            <p>Loading schedule...</p>
          </div>
        )}

        {/* Error */}
        {!isLoading && error && (
          <div className="schedule-error">
            <p className="schedule-error-title">Unable to load schedule</p>
            <p className="schedule-error-text">
              {error || "The schedule could not be loaded at the moment. Please try again later."}
            </p>
          </div>
        )}

         {/* Not published yet: show empty state even if sessions exist */}
         {!isLoading && !error && !isPublished && (
          <div className="schedule-empty-screen">
            <NoScheduleState />
          </div>
        )}

        {/* Published but no sessions */}
        {!isLoading && !error && isPublished && !hasSchedule && (
          <div className="schedule-empty-screen">
            <NoScheduleState />
          </div>
// =======
//         {/* EMPTY STATE */}
//         {!isLoading && !error && !hasSchedule && (
//             <div className="schedule-empty-screen">
//             <NoScheduleState status={semesterStatus} isSubmissionPeriod={isSubmissionPeriod} />
//             </div>
// >>>>>>> main
        )}

        {/* Published and has schedule: show grid */}
        {/* {!isLoading && !error && isPublished && hasSchedule && (
          <WeeklyScheduleGrid sessions={sessions} />
        )} */}
        {!isLoading && !error && isPublished && approvalStatus === "REJ" && (
          <div className="schedule-empty-screen">
            <NoScheduleState />
          </div>
        )}

        {!isLoading && !error && isPublished && hasSchedule && approvalStatus !== "REJ" && (
          <WeeklyScheduleGrid sessions={sessions} />
        )}


        <ConfirmModal
          open={approveOpen}
          title="Approve schedule?"
          message="You are about to approve the temporary schedule."
          confirmText="Approve"
          cancelText="Cancel"
          onCancel={() => setApproveOpen(false)}
          onConfirm={handleApprove}
          loading={isFeedbackSubmitting}
        />

        <ConfirmModal
          open={rejectOpen}
          title="Reject schedule?"
          message="You are about to reject the temporary schedule. You will be redirected to update your constraints."
          confirmText="Reject"
          cancelText="Cancel"
          onCancel={() => setRejectOpen(false)}
          onConfirm={handleReject}
          loading={isFeedbackSubmitting}
        />
      </div>
    </div>
  );
}

export default SchedulePage;
