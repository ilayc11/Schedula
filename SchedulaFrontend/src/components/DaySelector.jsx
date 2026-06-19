import PropTypes from "prop-types";
import "./DaySelector.css";

const DAY_OPTIONS = [
  { value: 1, label: "Sun" },
  { value: 2, label: "Mon" },
  { value: 3, label: "Tue" },
  { value: 4, label: "Wed" },
  { value: 5, label: "Thu" },
  { value: 6, label: "Fri" },
];

export default function DaySelector({ days, onChange, disabled = false, error }) {
  const selected = new Set(Array.isArray(days) ? days : []);

  const toggle = (value) => {
    if (disabled) return;
    const next = new Set(selected);
    if (next.has(value)) {
      next.delete(value);
    } else {
      next.add(value);
    }
    const arr = Array.from(next).sort((a, b) => a - b);
    onChange(arr);
  };

  return (
    <div className={`day-selector ${error ? "day-selector-error" : ""}`}>
      <div className="day-selector-chips" role="group" aria-label="Days of week">
        {DAY_OPTIONS.map((opt) => {
          const isOn = selected.has(opt.value);
          return (
            <button
              key={opt.value}
              type="button"
              className={`day-chip ${isOn ? "day-chip-on" : ""}`}
              onClick={() => toggle(opt.value)}
              disabled={disabled}
              aria-pressed={isOn}
            >
              {opt.label}
            </button>
          );
        })}
      </div>
      {error ? <div className="day-selector-error-text">{error}</div> : null}
    </div>
  );
}

DaySelector.propTypes = {
  days: PropTypes.arrayOf(PropTypes.number),
  onChange: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
  error: PropTypes.string,
};
