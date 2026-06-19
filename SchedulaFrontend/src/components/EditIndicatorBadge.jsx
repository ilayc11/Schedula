import PropTypes from "prop-types";
import Tooltip from "./Tooltip.jsx";
import "./EditIndicatorBadge.css";

export default function EditIndicatorBadge({
  isEdited,
  originalRawText,
  className = "",
}) {
  if (!isEdited) return null;

  const tooltipText = originalRawText
    ? `This constraint has been manually modified. Original text was: "${originalRawText}"`
    : "This constraint has been manually modified.";

  return (
    <Tooltip text={tooltipText}>
      <span
        className={`edit-indicator-badge ${className}`}
        role="img"
        aria-label="Manually modified by secretary"
      >
        <span className="edit-indicator-dot" aria-hidden="true">
          ✎
        </span>
        <span className="edit-indicator-text">Manually modified</span>
      </span>
    </Tooltip>
  );
}

EditIndicatorBadge.propTypes = {
  isEdited: PropTypes.bool,
  originalRawText: PropTypes.string,
  className: PropTypes.string,
};
