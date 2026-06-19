import PropTypes from "prop-types";
import "./ConfirmModal.css";

export default function ConfirmModal({
  open,
  title,
  message,
  confirmText = "Yes",
  cancelText = "Cancel",
  onConfirm,
  onCancel,
  loading = false,
}) {
  if (!open) return null;

  return (
    <div className="cm-backdrop" onClick={onCancel} role="presentation">
      <div className="cm-card" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="cm-title">{title}</div>
        <div className="cm-message">{message}</div>

        <div className="cm-actions">
          <button type="button" className="button button-secondary" onClick={onCancel} disabled={loading}>
            {cancelText}
          </button>
          <button type="button" className="button button-primary" onClick={onConfirm} disabled={loading}>
            {loading ? "Working..." : confirmText}
          </button>
        </div>
      </div>
    </div>
  );
}

ConfirmModal.propTypes = {
  open: PropTypes.bool.isRequired,
  title: PropTypes.string,
  message: PropTypes.string,
  confirmText: PropTypes.string,
  cancelText: PropTypes.string,
  onConfirm: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired,
  loading: PropTypes.bool,
};
