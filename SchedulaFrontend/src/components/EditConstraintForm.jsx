import PropTypes from "prop-types";
import { useMemo, useState } from "react";
import DaySelector from "./DaySelector.jsx";
import { validateDays } from "./DaySelector.utils.js";
import TimeSlotEditor from "./TimeSlotEditor.jsx";
import { validateTimeSlot } from "./TimeSlotEditor.utils.js";
import Tooltip from "./Tooltip.jsx";
import "./EditConstraintForm.css";

const TYPE_LABELS = {
  block: "BLOCK",
  preference: "PREFERENCE",
};

function defaultAtomic(typeOverride) {
  return {
    type: typeOverride || "block",
    days: [1],
    time_slot: { start_hour: 8, start_minute: 0, end_hour: 10, end_minute: 0 },
    priority: "soft",
    __isNew: true,
  };
}

function cloneAtomicsForEditing(atomics) {
  if (!Array.isArray(atomics)) return [];
  return atomics.map((a) => {
    const ts = a.time_slot;
    const time_slot = ts
      ? {
          start_hour: Number(ts.start_hour ?? 0),
          start_minute: Number(ts.start_minute ?? 0),
          end_hour: Number(ts.end_hour ?? 0),
          end_minute: Number(ts.end_minute ?? 0),
        }
      : null;
    return {
      type: a.type === "preference" ? "preference" : "block",
      days: Array.isArray(a.days) ? [...a.days] : [],
      time_slot,
      priority: a.priority === "hard" ? "hard" : "soft",
      __isNew: false,
    };
  });
}

function stripForApi(atomics) {
  return atomics.map((a) => ({
    type: a.type,
    days: [...a.days].sort((x, y) => x - y),
    time_slot: a.time_slot,
    priority: a.priority,
  }));
}

function validateAll(atomics) {
  const errors = atomics.map((a) => {
    const dayErr = validateDays(a.days);
    const tsErr = validateTimeSlot(a.time_slot);
    return { days: dayErr, time_slot: tsErr };
  });
  const hasError = errors.some((e) => e.days || e.time_slot);
  return { errors, hasError };
}

export default function EditConstraintForm({
  open,
  constraint,
  onCancel,
  onSave,
  loading = false,
  error: externalError = "",
}) {
  const initialAtomics = useMemo(() => {
    const fromConstraint =
      constraint?.structured_rules?.atomic_constraints ?? [];
    const cloned = cloneAtomicsForEditing(fromConstraint);
    return cloned.length > 0 ? cloned : [defaultAtomic("block")];
  }, [constraint]);

  const [atomics, setAtomics] = useState(initialAtomics);
  const [rawText, setRawText] = useState("");
  const [touched, setTouched] = useState(false);

  // Reset internal state when the modal opens for a (possibly different)
  // constraint. Following React's "Adjusting state when a prop changes"
  // pattern lets us avoid setState inside useEffect.
  const [prevOpen, setPrevOpen] = useState(open);
  const [prevConstraintId, setPrevConstraintId] = useState(
    constraint?.constraints_id ?? null
  );
  if (
    open !== prevOpen ||
    (constraint?.constraints_id ?? null) !== prevConstraintId
  ) {
    setPrevOpen(open);
    setPrevConstraintId(constraint?.constraints_id ?? null);
    if (open) {
      setAtomics(initialAtomics);
      setRawText("");
      setTouched(false);
    }
  }

  const { errors, hasError } = useMemo(() => validateAll(atomics), [atomics]);
  const showErrors = touched;
  const formError =
    showErrors && atomics.length === 0
      ? "At least one atomic constraint is required"
      : "";

  if (!open) return null;

  const updateAtomic = (idx, patch) => {
    setAtomics((curr) => curr.map((a, i) => (i === idx ? { ...a, ...patch } : a)));
  };

  const removeAtomic = (idx) => {
    setAtomics((curr) => curr.filter((_, i) => i !== idx));
  };

  const addAtomic = () => {
    setAtomics((curr) => [...curr, defaultAtomic("block")]);
  };

  const handleSubmit = async () => {
    setTouched(true);
    if (hasError || atomics.length === 0) return;
    const payload = {
      structured_rules: {
        atomic_constraints: stripForApi(atomics),
      },
      raw_text: rawText.trim() || null,
    };
    await onSave(payload);
  };

  return (
    <div
      className="ecf-backdrop"
      onClick={loading ? undefined : onCancel}
      role="presentation"
    >
      <div
        className="ecf-card"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Edit structured rules"
      >
        <div className="ecf-head">
          <div className="ecf-title">
            Edit structured rules
            {constraint?.constraints_id ? (
              <span className="ecf-id"> #{constraint.constraints_id}</span>
            ) : null}
          </div>
          <div className="ecf-sub">
            Add, edit, or delete atomic constraints. The type (block / preference)
            of an existing atomic is locked.
          </div>
        </div>

        {externalError ? <div className="ecf-error">{externalError}</div> : null}
        {formError ? <div className="ecf-error">{formError}</div> : null}

        <div className="ecf-list">
          {atomics.map((a, idx) => {
            const e = errors[idx] || {};
            const typeLocked = !a.__isNew;
            return (
              <div key={idx} className="ecf-atomic">
                <div className="ecf-atomic-head">
                  <Tooltip
                    text={
                      typeLocked
                        ? "Type is locked for existing atomics; you can still adjust days, hours, and priority."
                        : "Pick the type for this new atomic. After save, the type will be locked."
                    }
                  >
                    <span
                      className={`ecf-type-pill ecf-type-${a.type} ${
                        typeLocked ? "ecf-type-locked" : ""
                      }`}
                    >
                      {TYPE_LABELS[a.type] || a.type}
                      {typeLocked ? <span className="ecf-lock"> 🔒</span> : null}
                    </span>
                  </Tooltip>

                  {!typeLocked && (
                    <select
                      className="ecf-type-select"
                      value={a.type}
                      onChange={(ev) =>
                        updateAtomic(idx, { type: ev.target.value })
                      }
                      disabled={loading}
                      aria-label="Atomic type"
                    >
                    <option value="block">Block</option>
                    <option value="preference">Preference</option>
                    </select>
                  )}

                  <button
                    type="button"
                    className="ecf-remove"
                    onClick={() => removeAtomic(idx)}
                    disabled={loading}
                    aria-label="Remove atomic constraint"
                  >
                    Remove
                  </button>
                </div>

                <div className="ecf-row">
                  <div className="ecf-row-label">Days</div>
                  <DaySelector
                    days={a.days}
                    onChange={(next) => updateAtomic(idx, { days: next })}
                    disabled={loading}
                    error={showErrors ? e.days : undefined}
                  />
                </div>

                <div className="ecf-details-grid">
                  <div className="ecf-row ecf-time-section">
                    <div className="ecf-row-label">Time</div>
                    <TimeSlotEditor
                      timeSlot={a.time_slot}
                      onChange={(next) => updateAtomic(idx, { time_slot: next })}
                      disabled={loading}
                      error={showErrors ? e.time_slot : undefined}
                    />
                  </div>

                  <div className="ecf-row ecf-priority-card">
                    <div className="ecf-row-label">Priority</div>
                    <select
                      className="ecf-priority"
                      value={a.priority}
                      onChange={(ev) =>
                        updateAtomic(idx, { priority: ev.target.value })
                      }
                      disabled={loading}
                    >
                      <option value="soft">Preferred</option>
                      <option value="hard">Required</option>
                    </select>
                  </div>
                </div>

                {/* <div className="ecf-row">
                  <div className="ecf-row-label">Time</div>
                  <TimeSlotEditor
                    timeSlot={a.time_slot}
                    onChange={(next) => updateAtomic(idx, { time_slot: next })}
                    disabled={loading}
                    error={showErrors ? e.time_slot : undefined}
                  />
                </div>

                <div className="ecf-row">
                  <div className="ecf-row-label">Priority</div>
                  <select
                    className="ecf-priority"
                    value={a.priority}
                    onChange={(ev) =>
                      updateAtomic(idx, { priority: ev.target.value })
                    }
                    disabled={loading}
                  >
                    <option value="soft">soft</option>
                    <option value="hard">hard</option>
                  </select>
                </div> */}
              </div>
            );
          })}
        </div>

        <div className="ecf-add-row">
          <button
            type="button"
            className="button button-secondary"
            onClick={addAtomic}
            disabled={loading}
          >
            + Add atomic constraint
          </button>
        </div>

        <div className="ecf-text-row">
          <label className="ecf-text-label" htmlFor="ecf-raw-text">
            New constraint text (optional)
          </label>
          <textarea
            id="ecf-raw-text"
            className="ecf-textarea"
            placeholder="Leave empty to auto-generate a preview from the rules."
            value={rawText}
            onChange={(e) => setRawText(e.target.value)}
            disabled={loading}
          />
        </div>

        <div className="ecf-actions">
          <button
            type="button"
            className="button button-secondary"
            onClick={onCancel}
            disabled={loading}
          >
            Cancel
          </button>
          <button
            type="button"
            className="button button-primary"
            onClick={handleSubmit}
            disabled={loading || atomics.length === 0}
          >
            {loading ? "Saving..." : "Save changes"}
          </button>
        </div>
      </div>
    </div>
  );
}

EditConstraintForm.propTypes = {
  open: PropTypes.bool.isRequired,
  constraint: PropTypes.shape({
    constraints_id: PropTypes.number,
    structured_rules: PropTypes.object,
  }),
  onCancel: PropTypes.func.isRequired,
  onSave: PropTypes.func.isRequired,
  loading: PropTypes.bool,
  error: PropTypes.string,
};
