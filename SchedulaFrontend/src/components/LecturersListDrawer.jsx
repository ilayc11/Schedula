import PropTypes from "prop-types";
import "./LecturersListDrawer.css";

function fullName(p) {
  const f = String(p?.first_name || "").trim();
  const l = String(p?.last_name || "").trim();
  return `${f} ${l}`.trim() || "Unknown lecturer";
}

function LecturersListDrawer({ open, title, items, onClose }) {
  if (!open) return null;

  const list = Array.isArray(items) ? items : [];

  const copyAllEmails = async () => {
    const emails = list.map((x) => x?.email).filter(Boolean).join(", ");
    if (!emails) return;
    try {
      await navigator.clipboard.writeText(emails);
    } catch {
      // ignore
    }
  };

  return (
    <div className="lld-backdrop" onClick={onClose} role="presentation">
      <aside
        className="lld-panel"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="lld-head">
          <div className="lld-title">{title}</div>
          <button type="button" className="lld-close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>

        {list.length === 0 ? (
          <div className="lld-empty">No lecturers in this list.</div>
        ) : (
          <div className="lld-list">
            {list.map((p, idx) => (
              <div key={p?.email || idx} className="lld-item">
                <div className="lld-name">{fullName(p)}</div>
                {p?.email && <div className="lld-email">{p.email}</div>}
              </div>
            ))}
          </div>
        )}

        <div className="lld-actions">
          <button
            type="button"
            className="lld-btn"
            onClick={copyAllEmails}
            disabled={list.length === 0}
          >
            Copy all emails
          </button>
        </div>
      </aside>
    </div>
  );
}

LecturersListDrawer.propTypes = {
  open: PropTypes.bool.isRequired,
  title: PropTypes.string.isRequired,
  items: PropTypes.array,
  onClose: PropTypes.func.isRequired,
};

export default LecturersListDrawer;
