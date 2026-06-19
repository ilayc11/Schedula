// src/components/dashboard/CollaborationStatsCard.jsx
import { useEffect, useMemo, useState } from "react";
import PropTypes from "prop-types";
import { useMockMode } from "../context/MockModeContext.jsx";
import "./CollaborationStatsCard.css";
import LecturersListDrawer from "./LecturersListDrawer";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const SECRETARY_PREFIX = import.meta.env.VITE_API_PREFIX_SECRETARY || "/secretary";

// Mock data remains the same
const MOCK_CONSTRAINTS_STATS = {
  total_lecturers: 24,
  submitted_count: 17, 
  missing_lecturers: [{}, {}, {}, {}, {}, {}, {}],
};

const MOCK_CHANGES_STATS = {
  total_lecturers: 24,
  approved: 12,
  rejected: 6, 
  pending: 6,
};

function getToken() {
  return localStorage.getItem("access_token");
}

function clampToNonNegativeInt(n) {
  const x = Number(n);
  if (!Number.isFinite(x) || x < 0) return 0;
  return Math.floor(x);
}

function percent(part, total) {
  if (!total) return 0;
  return Math.round((part / total) * 100);
}

// function BarRow({ label, value, total }) {
//   const pct = percent(value, total);
//   return (
//     <div className="collab-row">
//       <div className="collab-row-top">
//         <span className="collab-label">{label}</span>
//         <span className="collab-value">{value}/{total} ({pct}%)</span>
//       </div>
//       <div className="collab-bar">
//         <div className="collab-bar-fill" style={{ width: `${pct}%` }} />
//       </div>
//     </div>
//   );
// }
function BarRow({ label, value, total, onClick, clickable }) {
  const pct = percent(value, total);

  return (
    <div
      className={`collab-row ${clickable ? "collab-row-clickable" : ""}`}
      onClick={clickable ? onClick : undefined}
      role={clickable ? "button" : undefined}
      tabIndex={clickable ? 0 : undefined}
      onKeyDown={(e) => {
        if (!clickable) return;
        if (e.key === "Enter" || e.key === " ") onClick?.();
      }}
    >
      <div className="collab-row-top">
        <span className="collab-label">{label}</span>
        <span className="collab-value">{value}/{total} ({pct}%)</span>
      </div>
      <div className="collab-bar">
        <div className="collab-bar-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
BarRow.propTypes = {
  label: PropTypes.string.isRequired,
  value: PropTypes.number.isRequired,
  total: PropTypes.number.isRequired,
  onClick: PropTypes.func,
  clickable: PropTypes.bool,
};


function getModeBySemesterStatus(semesterStatus) {
  if (semesterStatus === "SUB") return "constraints";
  if (semesterStatus === "CHA") return "changes";
  return "none";
}

function CollaborationStatsCard({ semesterYear, semesterNumber, semesterStatus }) {
  const { useMock } = useMockMode();
  const [stats, setStats] = useState(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerTitle, setDrawerTitle] = useState("");
  const [drawerItems, setDrawerItems] = useState([]);

  const openDrawer = (titleText, items) => {
    setDrawerTitle(titleText);
    setDrawerItems(Array.isArray(items) ? items : []);
    setDrawerOpen(true);
  };

  const closeDrawer = () => {
    setDrawerOpen(false);
  };

  const mode = useMemo(() => getModeBySemesterStatus(semesterStatus), [semesterStatus]);

  useEffect(() => {
    let alive = true;

    async function load() {
      if (mode === "none") {
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      setError("");

      try {
        if (useMock) {
          await new Promise((r) => setTimeout(r, 250));
          if (!alive) return;
          setStats(mode === "constraints" ? MOCK_CONSTRAINTS_STATS : MOCK_CHANGES_STATS);
          setIsLoading(false);
          return;
        }

        const token = getToken();
        if (!token) throw new Error("Not authenticated");

        const url = `${API_BASE_URL}${SECRETARY_PREFIX}/dashboard/stats`;

        const res = await fetch(url, {
          method: "GET",
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!res.ok) {
          const data = await res.json().catch(() => null);
          throw new Error(data?.detail || `Error ${res.status}`);
        }

        const data = await res.json();
        if (!alive) return;
        setStats(data);
      } catch (e) {
        if (!alive) return;
        setError(e.message || "Failed to load collaboration stats");
      } finally {
        if (alive) setIsLoading(false);
      }
    }

    load();
    return () => { alive = false; };
  }, [useMock, mode, semesterYear, semesterNumber]);

  const title = mode === "constraints"
    ? "Lecturer Collaboration: Constraint Submission"
    : "Lecturer Collaboration: Schedule Approval";

  if (isLoading) return <div className="card collab-card"><h2 className="collab-title">{title}</h2><p>Loading...</p></div>;
  if (mode === "none") return <div className="card collab-card"><h2 className="collab-title">Lecturer Collaboration</h2><p>Stats will be available during submission or approval stages.</p></div>;
  if (error) return <div className="card collab-card"><h2 className="collab-title">{title}</h2><p className="collab-error">{error}</p></div>;
  if (!stats) return null;

  const total = clampToNonNegativeInt(stats.total_lecturers);
  const missingList = Array.isArray(stats?.missing_lecturers) ? stats.missing_lecturers : [];
  const rejectedList = Array.isArray(stats?.rejected_lecturers) ? stats.rejected_lecturers : [];
  const pendingList = Array.isArray(stats?.pending_lecturers) ? stats.pending_lecturers : [];
  const approvedList = Array.isArray(stats?.approved_lecturers) ? stats.approved_lecturers : [];


  const rows = mode === "constraints"
    ? [
        { label: "Submitted constraints", value: clampToNonNegativeInt(stats.submitted_count) },
        { label: "Not submitted yet", value: total - clampToNonNegativeInt(stats.submitted_count) },
      ]
    : [
        { label: "Approved schedule", value: clampToNonNegativeInt(stats.approved) },
        { label: "Rejected/Changes", value: clampToNonNegativeInt(stats.rejected) },
        { label: "No response yet", value: clampToNonNegativeInt(stats.pending) },
      ];

      const completed = mode === "constraints"
  ? clampToNonNegativeInt(stats.submitted_count)
  : clampToNonNegativeInt(stats.approved);

const completionPct = percent(completed, total);

return (
  <div className="card collab-card collab-card-polished">
    <div className="collab-header">
      <div className="collab-icon">👥</div>
      <h2 className="collab-title">{title}</h2>
    </div>

    <div className="collab-polished-body">
      <div className="collab-main-stats">
        <div className="collab-stat-box">
          <span>Total lecturers</span>
          <strong>{total}</strong>
        </div>

        <div className="collab-stat-box">
          <span>{mode === "constraints" ? "Submitted constraints" : "Approved schedules"}</span>
          <strong>
            {completed} <em>/ {total}</em>
          </strong>
        </div>

        <div className="collab-rows">
          {rows.map((r) => {
            const clickConfigByLabel = {
              "Not submitted yet": {
                title: "Lecturers who did not submit constraints",
                items: missingList,
                enabled: mode === "constraints",
              },
              "Rejected/Changes": {
                title: "Lecturers who rejected the schedule",
                items: rejectedList,
                enabled: mode === "changes",
              },
              "No response yet": {
                title: "Lecturers with no response yet",
                items: pendingList,
                enabled: mode === "changes",
              },
              "Approved schedule": {
                title: "Lecturers who approved the schedule",
                items: approvedList,
                enabled: mode === "changes",
              },
            };

            const cfg = clickConfigByLabel[r.label];
            const clickable = Boolean(cfg?.enabled && cfg?.items?.length);

            return (
              <BarRow
                key={r.label}
                label={r.label}
                value={r.value}
                total={total}
                clickable={clickable}
                onClick={clickable ? () => openDrawer(cfg.title, cfg.items) : undefined}
              />
            );
          })}
        </div>
      </div>

      <div className="collab-ring" style={{ "--pct": `${completionPct}%` }}>
        <div className="collab-ring-inner">
          <strong>{completionPct}%</strong>
          <span>Completed</span>
        </div>
      </div>
    </div>

    <div className="collab-footer-note">
      {mode === "constraints"
        ? `${Math.max(total - completed, 0)} lecturers still need to submit their constraints.`
        : `${Math.max(total - completed, 0)} lecturers still need to approve the schedule.`}
    </div>

    <LecturersListDrawer
      open={drawerOpen}
      title={drawerTitle}
      items={drawerItems}
      onClose={closeDrawer}
    />
  </div>
);

  // return (
  //   <div className="card collab-card">
  //     <h2 className="collab-title">{title}</h2>
  //     <div className="collab-body">
  //       <p className="collab-summary"><strong>Total lecturers:</strong> {total}</p>
  //       <div className="collab-rows">
  //         {/* {rows.map((r) => (
  //           <BarRow key={r.label} label={r.label} value={r.value} total={total} />
  //         ))} */}
  //         {/* {rows.map((r) => {
  //           const isMissingRow = mode === "constraints" && r.label === "Not submitted yet";
  //           const clickable = isMissingRow && missingList.length > 0;

  //           return (
  //             <BarRow
  //               key={r.label}
  //               label={r.label}
  //               value={r.value}
  //               total={total}
  //               clickable={clickable}
  //               onClick={
  //                 clickable
  //                   ? () => openDrawer("Lecturers who did not submit constraints", missingList)
  //                   : undefined}
  //             />
  //           );
  //         })} */}
  //         {rows.map((r) => {
  //           const clickConfigByLabel = {
  //             "Not submitted yet": {
  //               title: "Lecturers who did not submit constraints",
  //               items: missingList,
  //               enabled: mode === "constraints",
  //             },
  //             "Rejected/Changes": {
  //               title: "Lecturers who rejected the schedule",
  //               items: rejectedList,
  //               enabled: mode === "changes",
  //             },
  //             "No response yet": {
  //               title: "Lecturers with no response yet",
  //               items: pendingList,
  //               enabled: mode === "changes",
  //             },
  //             "Approved schedule": {
  //               title: "Lecturers who approved the schedule",
  //               items: approvedList,
  //               enabled: mode === "changes",
  //             },
  //           };

  //           const cfg = clickConfigByLabel[r.label];
  //           const clickable = Boolean(cfg?.enabled && cfg?.items?.length);

  //           return (
  //             <BarRow
  //               key={r.label}
  //               label={r.label}
  //               value={r.value}
  //               total={total}
  //               clickable={clickable}
  //               onClick={clickable ? () => openDrawer(cfg.title, cfg.items) : undefined}
  //             />
  //           );
  //         })}

  //       </div>
  //     </div>
  //     <LecturersListDrawer
  //       open={drawerOpen}
  //       title={drawerTitle}
  //       items={drawerItems}
  //       onClose={closeDrawer}
  //     />
  //   </div>
  // );
}

CollaborationStatsCard.propTypes = {
  semesterYear: PropTypes.number,
  semesterNumber: PropTypes.number,
  semesterStatus: PropTypes.string,
};

export default CollaborationStatsCard;