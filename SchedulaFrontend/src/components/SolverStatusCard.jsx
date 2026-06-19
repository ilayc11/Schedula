// src/components/SolverStatusCard.jsx
import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import PropTypes from "prop-types";
import "./SolverStatusCard.css";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const LECTURER_PREFIX = import.meta.env.VITE_API_PREFIX_LECTURER || "/lecturer";
const SECRETARY_PREFIX = import.meta.env.VITE_API_PREFIX_SECRETARY || "/secretary";

const POLL_INTERVAL_MS = 5000;

function getToken() {
  return localStorage.getItem("access_token");
}

function formatLastRun(isoString) {
  if (!isoString) return null;
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function SolverStatusCard({ semesterYear, semesterNumber, userRole = "lecturer" }) {
  const navigate = useNavigate();
  const [status, setStatus] = useState(null);
  const [error, setError] = useState("");
  const [isPolling, setIsPolling] = useState(false);

  const fetchStatus = useCallback(async () => {
    if (!semesterYear || !semesterNumber) return false;

    const token = getToken();
    if (!token) {
      setError("Not authenticated");
      return false;
    }

    try {
      let url = "";
      if (userRole === "secretary") {
        url = `${API_BASE_URL}${SECRETARY_PREFIX}/dashboard/solver_status?semester_year=${semesterYear}&semester_number=${semesterNumber}`;
      } else {
        url = `${API_BASE_URL}${LECTURER_PREFIX}/dashboard/solver_status?semester_year=${semesterYear}&semester_number=${semesterNumber}`;
      }

      const res = await fetch(url, {
        method: "GET",
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) {
        const data = await res.json().catch(() => null);
        throw new Error(data?.detail || `Error ${res.status}`);
      }

      const data = await res.json();
      setStatus(data);
      setError("");

      return data.status === "pending";
    } catch (e) {
      setError(e.message || "Failed to fetch solver status");
      return false;
    }
  }, [semesterYear, semesterNumber, userRole]);

  useEffect(() => {
    let intervalId = null;
    let mounted = true;

    async function startPolling() {
      const shouldContinue = await fetchStatus();
      if (!mounted) return;
      
      if (shouldContinue) {
        setIsPolling(true);
        intervalId = setInterval(async () => {
          if (!mounted) return;
          const keepPolling = await fetchStatus();
          if (!keepPolling && intervalId) {
            clearInterval(intervalId);
            setIsPolling(false);
          }
        }, POLL_INTERVAL_MS);
      }
    }

    startPolling();

    return () => {
      mounted = false;
      if (intervalId) clearInterval(intervalId);
    };
  }, [fetchStatus]);

  if (!semesterYear || !semesterNumber) {
    return (
      <div className="card solver-status-card">
        <h2 className="solver-title">Schedule Generation</h2>
        <div className="solver-loading"><div className="solver-spinner" /><span>Loading semester info...</span></div>
      </div>
    );
  }

  if (status === null && !error) {
    return (
      <div className="card solver-status-card">
        <h2 className="solver-title">Schedule Generation</h2>
        <div className="solver-loading"><div className="solver-spinner" /><span>Checking status...</span></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card solver-status-card solver-status-error">
        <h2 className="solver-title">Schedule Generation</h2>
        <div className="solver-error-content">
          <span className="solver-icon">⚠️</span>
          <p>{error}</p>
          <button className="button button-secondary" onClick={fetchStatus}>Retry</button>
        </div>
      </div>
    );
  }

  // logic for none/pending/solved/failed states...
  const isSec = userRole === "secretary";
  const lastRunAt = formatLastRun(status?.completed_at || status?.created_at);

  if (status.status === "none") {
    return (
      <div className="card solver-status-card solver-status-none">
        <h2 className="solver-title">Schedule Generation</h2>
        <div className="solver-content">
          <span className="solver-icon">📋</span>
          <p className="solver-message">No schedule generation triggered yet.</p>
          <button 
            className="button button-primary" 
            onClick={() => navigate(isSec ? "/secretary/schedules" : "/lecturer/constraints/write")}
          >
            {isSec ? "Go to Schedules" : "Submit Constraints"}
          </button>
        </div>
      </div>
    );
  }

  if (status.status === "pending") {
    return (
      <div className="card solver-status-card solver-status-pending">
        <h2 className="solver-title">Schedule Generation</h2>
        <div className="solver-content">
          <div className="solver-processing"><div className="solver-spinner-large" /><span className="solver-processing-text">Generating...</span></div>
          {isPolling && <p className="solver-polling-indicator"><span className="polling-dot" /> Live Monitoring...</p>}
        </div>
      </div>
    );
  }

  if (status.status === "solved") {
    return (
      <div className="card solver-status-card solver-status-solved">
        <h2 className="solver-title">Schedule Generation</h2>
        <div className="solver-content">
          <span className="solver-icon solver-icon-success">✓</span>
          <p className="solver-success-message">Schedule generated successfully!</p>
          {lastRunAt && (
            <p className="solver-timestamp">Last run: {lastRunAt}</p>
          )}
          <button className="button button-primary" onClick={() => navigate(isSec ? "/secretary/schedule-manager" : "/lecturer/schedule")}>
            View Schedule
          </button>
        </div>
      </div>
    );
  }

  if (status.status === "failed") {
    // failure_reason is populated by the backend so the UI can render an
    // actionable message tailored to the actual cause:
    //   - "user_constraints": one or more lecturer constraints conflict and
    //     are listed in broken_constraint_details. Existing flow.
    //   - "base_model": system-level hard constraints (no-overlap for
    //     lecturers/cohorts) are unsatisfiable on their own. Requires admin
    //     intervention; no individual lecturer constraint to point at.
    //   - "data_infeasible": cohort/lecturer load exceeds the weekly
    //     capacity. failure_details lists the over-subscribed entities.
    //   - undefined / null: legacy runs from before this field was added.
    const failureReason = status.failure_reason;
    const failureDetails = status.failure_details;
    const hasConflictDetails = Array.isArray(status.broken_constraint_details)
      && status.broken_constraint_details.length > 0;

    let headline = "Conflicts detected";
    if (failureReason === "data_infeasible") headline = "Schedule cannot be generated for this dataset";
    else if (failureReason === "base_model") headline = "Baseline scheduling rules are unsatisfiable";

    return (
      <div className="card solver-status-card solver-status-failed">
        <h2 className="solver-title">Schedule Generation</h2>
        <div className="solver-content">
          <span className="solver-icon solver-icon-failed">✕</span>
          <p className="solver-failed-message">{headline}</p>
          {lastRunAt && (
            <p className="solver-timestamp">Last run: {lastRunAt}</p>
          )}

          {failureReason === "data_infeasible" && failureDetails && (
            <div className="solver-conflicts">
              <p className="solver-failure-explanation">
                The course catalogue is over-subscribed: more class hours
                are required than fit into a single week
                {typeof failureDetails.weekly_capacity_hours === "number"
                  ? ` (${failureDetails.weekly_capacity_hours}h available)`
                  : ""}.
              </p>
              {Array.isArray(failureDetails.infeasible_cohorts) && failureDetails.infeasible_cohorts.length > 0 && (
                <>
                  <p className="conflicts-title">Over-subscribed cohorts</p>
                  <ul className="conflicts-list">
                    {failureDetails.infeasible_cohorts.slice(0, 8).map((c, idx) => (
                      <li key={`coh-${idx}`} className="conflict-item">
                        <strong>
                          Dept {c.cohort?.target_department_id} · Year {c.cohort?.target_year_level}
                        </strong>
                        : {c.required_hours}h needed / {c.available_hours}h available
                        {typeof c.course_count === "number" ? ` (${c.course_count} courses)` : ""}
                      </li>
                    ))}
                  </ul>
                </>
              )}
              {Array.isArray(failureDetails.infeasible_lecturers) && failureDetails.infeasible_lecturers.length > 0 && (
                <>
                  <p className="conflicts-title">Over-subscribed lecturers</p>
                  <ul className="conflicts-list">
                    {failureDetails.infeasible_lecturers.slice(0, 5).map((l, idx) => (
                      <li key={`lec-${idx}`} className="conflict-item">
                        <strong>Lecturer #{l.lecturer_internal_id}</strong>
                        : {l.required_hours}h needed / {l.available_hours}h available
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          )}

          {failureReason === "base_model" && (
            <div className="solver-conflicts">
              <p className="solver-failure-explanation">
                The system's baseline rules (lecturer no-overlap, cohort
                no-overlap) cannot be satisfied even before any lecturer
                constraint is applied. This usually means the course
                assignments themselves need review (duplicate groups,
                conflicting cohort targeting, or impossible course
                durations).
              </p>
            </div>
          )}

          {failureReason !== "data_infeasible" && failureReason !== "base_model" && hasConflictDetails && (
            <div className="solver-conflicts">
              <ul className="conflicts-list">
                {status.broken_constraint_details.map((c, idx) => (
                  <li key={idx} className="conflict-item">
                    <strong>{c.lecturer_name}:</strong> "{c.raw_text}"
                  </li>
                ))}
              </ul>
            </div>
          )}

          {failureReason === "data_infeasible" || failureReason === "base_model" ? (
            isSec ? (
              <button className="button button-primary" onClick={() => navigate("/secretary/schedules")}>
                Review Course Data
              </button>
            ) : null
          ) : (
            <button
              className="button button-primary"
              onClick={() => navigate(isSec ? "/secretary/constraints" : "/lecturer/constraints/manage")}
            >
              {isSec ? "Review Constraints" : "Edit My Constraints"}
            </button>
          )}
        </div>
      </div>
    );
  }

  return null;
}

SolverStatusCard.propTypes = {
  semesterYear: PropTypes.number,
  semesterNumber: PropTypes.number,
  userRole: PropTypes.oneOf(["lecturer", "secretary"]),
};

export default SolverStatusCard;