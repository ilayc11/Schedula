import PropTypes from "prop-types";
import "./StatusToast.css";

export default function StatusToast({
  open,
  title = "Done",
  message,
  onClose,
  actionText = "OK",
  type = "success", // success | error | info
}) {
  if (!open) return null;

  return (
    <div className="st-backdrop" onClick={onClose} role="presentation">
      <div
        className={`st-card st-${type}`}
        onClick={(e) => e.stopPropagation()}
        role="status"
        aria-live="polite"
      >
        <div className="st-title">{title}</div>
        <div className="st-message">{message}</div>

        <div className="st-actions">
          <button type="button" className="button button-primary" onClick={onClose}>
            {actionText}
          </button>
        </div>
      </div>
    </div>
  );
}

StatusToast.propTypes = {
  open: PropTypes.bool.isRequired,
  title: PropTypes.string,
  message: PropTypes.string.isRequired,
  onClose: PropTypes.func.isRequired,
  actionText: PropTypes.string,
  type: PropTypes.oneOf(["success", "error", "info"]),
};
