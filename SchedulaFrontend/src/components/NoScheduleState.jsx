// src/components/NoScheduleState.jsx
import "./NoScheduleState.css";

function NoScheduleState({ status, isSubmissionPeriod }) {
  // If in constraint submission period, show specific message
  if (isSubmissionPeriod || status === "SUB") {
    return (
      <div className="no-schedule">
        <h2 className="no-schedule-title">Schedule Hidden During Constraint Submission</h2>
        <p className="no-schedule-text">
          Schedules are not visible during the constraint submission period.
          Please focus on submitting your constraints. The schedule will be
          available once the submission period ends.
        </p>
      </div>
    );
  }

  // Default message for other cases
  return (
    <div className="no-schedule">
      <h2 className="no-schedule-title">Schedule not available yet</h2>
      <p className="no-schedule-text">
        Once the schedule is published, it will appear here automatically.
      </p>
    </div>
  );
}

export default NoScheduleState;
