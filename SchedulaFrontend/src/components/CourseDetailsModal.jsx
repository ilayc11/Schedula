import PropTypes from "prop-types";
import "./CourseDetailsModal.css";

const DAY_LABELS = {
  1: "Sunday",
  2: "Monday",
  3: "Tuesday",
  4: "Wednesday",
  5: "Thursday",
  6: "Friday",
};

function formatTime(hhmm) {
  return String(hhmm).slice(0, 5);
}

export default function CourseDetailsModal({ session, onClose }) {
  if (!session) return null;

  const cohorts = Array.isArray(session.cohorts) ? session.cohorts : [];

  return (
    <div className="cdm-backdrop" onClick={onClose} role="presentation">
      <div
        className="cdm-card"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={`${session.course_name} details`}
      >
        <div className="cdm-header">
          <div>
            <div className="cdm-title">{session.course_name}</div>
            {session.course_number != null && (
              <div className="cdm-subtitle">#{session.course_number}</div>
            )}
          </div>
          <button
            type="button"
            className="cdm-close"
            onClick={onClose}
            aria-label="Close"
          >
            ✕
          </button>
        </div>

        <dl className="cdm-details">
          {session.day_of_week != null && (
            <div className="cdm-row">
              <dt>Day</dt>
              <dd>{DAY_LABELS[session.day_of_week] ?? session.day_of_week}</dd>
            </div>
          )}

          <div className="cdm-row">
            <dt>Time</dt>
            <dd>
              {formatTime(session.start_time)} – {formatTime(session.end_time)}
            </dd>
          </div>

          {session.lecturer_name && (
            <div className="cdm-row">
              <dt>Lecturer</dt>
              <dd>{session.lecturer_name}</dd>
            </div>
          )}

          {session.group_number != null && (
            <div className="cdm-row">
              <dt>Group</dt>
              <dd>{session.group_number}</dd>
            </div>
          )}

          {cohorts.length > 0 && (
            <div className="cdm-row">
              <dt>Cohorts</dt>
              <dd>
                <div className="cdm-chips">
                  {cohorts.map((cohort, index) => (
                    <span
                      key={`${cohort.target_department_id}-${cohort.target_year_level}-${index}`}
                      className="cdm-chip"
                    >
                      Dept {cohort.target_department_id} · Year {cohort.target_year_level}
                    </span>
                  ))}
                </div>
              </dd>
            </div>
          )}
        </dl>

        <div className="cdm-actions">
          <button type="button" className="button button-primary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

CourseDetailsModal.propTypes = {
  session: PropTypes.object,
  onClose: PropTypes.func.isRequired,
};
