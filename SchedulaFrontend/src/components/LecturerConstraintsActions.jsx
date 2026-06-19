// src/components/dashboard/LecturerConstraintsActions.jsx
import { useNavigate } from "react-router-dom";
import PropTypes from "prop-types";

function LecturerConstraintsActions({ status }) {
  const navigate = useNavigate();

  const canSubmitConstraints = status === "SUB" || status === "CHA";
  const canEditConstraints = status === "SUB" || status === "CHA";

  if (!canSubmitConstraints && !canEditConstraints) {
    return null;
  }

  return (
    <div className="system-actions">
      {canSubmitConstraints && (
        <button
          className="button button-primary"
          onClick={() => navigate("/lecturer/constraints/write")}
        >
          Submit Constraints
        </button>
      )}

      {canEditConstraints && (
        <button
          className="button button-secondary"
          onClick={() => navigate("/lecturer/constraints/manage")}
        >
          View & Edit Constraints
        </button>
      )}
    </div>
  );
}

LecturerConstraintsActions.propTypes = {
  status: PropTypes.string.isRequired,
};

export default LecturerConstraintsActions;
