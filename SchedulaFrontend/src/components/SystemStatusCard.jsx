// src/components/dashboard/SystemStatusCard.jsx
import { useEffect, useState } from "react";
import { useMockMode } from "../context/MockModeContext.jsx";
import PropTypes from "prop-types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const LECTURER_PREFIX = import.meta.env.VITE_API_PREFIX_LECTURER || "/lecturer";
const SECRETARY_PREFIX = import.meta.env.VITE_API_PREFIX_SECRETARY || "/secretary";

// Mock data
const MOCK_SEMESTER = {
  semester_year: 2026,
  semester_number: 1,
  status: "SUB", // Possible statuses: SET, SUB, REV, CHA, PUB
  constraint_end_date: "2026-11-20",
};

const STATUS_LABELS = {
  SET: "Setup - Schedule being configured",
  SUB: "Open - Constraint submission is active",
  REV: "Review - Constraints under review",
  CHA: "Changes - Schedule adjustments in progress",
  PUB: "Published - Final schedule released",
};

const SEMESTER_NAMES = {
  1: "Fall",
  2: "Spring",
  3: "Summer",
};

function formatDeadline(dateStr) {
  if (!dateStr) return "Not set";
  const date = new Date(dateStr);
  return date.toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

function SystemStatusCard({ onSemesterLoaded, userRole = "lecturer" }) {
  const { useMock } = useMockMode();
  const [semester, setSemester] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;

    async function load() {
      setIsLoading(true);
      setError("");

      try {
        if (useMock) {
          await new Promise((resolve) => setTimeout(resolve, 300));
          if (!alive) return;
          setSemester(MOCK_SEMESTER);
          try {
            localStorage.setItem(
              "current_semester",
              JSON.stringify({
                semester_year: MOCK_SEMESTER.semester_year,
                semester_number: MOCK_SEMESTER.semester_number,
                status: MOCK_SEMESTER.status,
                constraint_end_date: MOCK_SEMESTER.constraint_end_date,
                updated_at: new Date().toISOString(),
              })
            );
          } catch {}

          onSemesterLoaded?.(MOCK_SEMESTER);
          setIsLoading(false);
          return;
        }

        const token = localStorage.getItem("access_token");
        if (!token) throw new Error("Not authenticated");

        // לוגיקת בחירת ה-Endpoint
        let endpoint = "";
        if (userRole === "secretary") {
          endpoint = `${API_BASE_URL}${SECRETARY_PREFIX}/dashboard/semester_info`;
        } else {
          endpoint = `${API_BASE_URL}${LECTURER_PREFIX}/dashboard/current_semester`;
        }

        const res = await fetch(endpoint, {
          method: "GET",
          headers: {
            Authorization: `Bearer ${token}`,
          },
        });

        if (!res.ok) {
          const data = await res.json().catch(() => null);
          throw new Error(data?.detail || `Error ${res.status}`);
        }

        const data = await res.json();
        if (!alive) return;
        setSemester(data);
        try {
          localStorage.setItem(
            "current_semester",
            JSON.stringify({
              semester_year: data.semester_year,
              semester_number: data.semester_number,
              status: data.status,
              constraint_end_date: data.constraint_end_date,
              updated_at: new Date().toISOString(),
            })
          );
        } catch {}

        onSemesterLoaded?.(data);
      } catch (e) {
        if (!alive) return;
        setError(e.message || "Failed to load semester status");
      } finally {
        if (alive) setIsLoading(false);
      }
    }

    load();
    return () => { alive = false; };
  }, [useMock, userRole]); 

  if (isLoading) 
    return 
      <div className="card system-status-card">
      <h2 className="system-title">System Status</h2>
      <p>Loading...</p></div>;
  if (error) 
    return 
      <div className="card system-status-card">
      <h2 className="system-title">System Status</h2>
      <p style={{ color: "red" }}>{error}</p></div>;
  if (!semester) 
    return 
      <div className="card system-status-card">
      <h2 className="system-title">System Status</h2>
      <p>No active semester found.</p></div>;

  const semesterName = SEMESTER_NAMES[semester.semester_number] || `Semester ${semester.semester_number}`;
  const statusLabel = STATUS_LABELS[semester.status] || semester.status;

  // return (
  //   <div className="card system-status-card">
  //     <h2 className="system-title">System Status</h2>
  //     <div className="system-info">
  //       <p><strong>Current semester:</strong> {semesterName} {semester.semester_year}</p>
  //       <p><strong>Status:</strong> {statusLabel}</p>
  //       <p><strong>Deadline:</strong> {formatDeadline(semester.constraint_end_date)}</p>
  //     </div>
  //   </div>
  // );
    return (
    <div className="card system-status-card system-status-polished">
      <div className="status-card-header">
        <div className="status-icon status-icon-blue">▣</div>
        <h2 className="system-title">Semester Status</h2>
      </div>

      <div className="system-status-grid">
        <div className="system-status-item">
          <div className="status-icon status-icon-soft-blue">▣</div>
          <div>
            <span className="status-label">Current semester</span>
            <strong>{semesterName} {semester.semester_year}</strong>
          </div>
        </div>

        <div className="system-status-item">
          <div className="status-icon status-icon-soft-green">✓</div>
          <div>
            <span className="status-label">Status</span>
            {/* <strong className="status-badge">Open</strong> */}
            <strong className="status-badge">{semester.status}</strong>
            <p>{statusLabel.replace("Open - ", "")}</p>
          </div>
        </div>

        <div className="system-status-item">
          <div className="status-icon status-icon-soft-purple">◷</div>
          <div>
            <span className="status-label">Deadline</span>
            <strong>{formatDeadline(semester.constraint_end_date)}</strong>
          </div>
        </div>
      </div>
    </div>
  );
}

SystemStatusCard.propTypes = {
  onSemesterLoaded: PropTypes.func,
  userRole: PropTypes.oneOf(["lecturer", "secretary"]),
};

export default SystemStatusCard;