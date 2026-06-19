import PropTypes from "prop-types";
import { useCallback, useMemo } from "react";
import "./TimeSlotEditor.css";

const HOUR_OPTIONS_END = Array.from({ length: 25 }, (_, h) => h);
const HOUR_OPTIONS_START = Array.from({ length: 24 }, (_, h) => h);
const MINUTE_STEPS = [0, 15, 30, 45];

function buildMinuteOptions(currentMinute) {
  const set = new Set(MINUTE_STEPS);
  if (Number.isInteger(currentMinute)) set.add(currentMinute);
  return Array.from(set).sort((a, b) => a - b);
}

function pad2(n) {
  return String(n ?? 0).padStart(2, "0");
}

export default function TimeSlotEditor({ timeSlot, onChange, error, disabled = false }) {
  const isFullDay = timeSlot === null || timeSlot === undefined;

  const startMinuteOptions = useMemo(
    () => buildMinuteOptions(timeSlot?.start_minute),
    [timeSlot?.start_minute]
  );
  const endMinuteOptions = useMemo(
    () => buildMinuteOptions(timeSlot?.end_minute),
    [timeSlot?.end_minute]
  );

  const handleFullDayToggle = useCallback(() => {
    if (disabled) return;
    if (isFullDay) {
      onChange({ start_hour: 8, start_minute: 0, end_hour: 10, end_minute: 0 });
    } else {
      onChange(null);
    }
  }, [isFullDay, onChange, disabled]);

  const handleFieldChange = useCallback(
    (field, value) => {
      if (disabled || !timeSlot) return;
      onChange({ ...timeSlot, [field]: Number(value) });
    },
    [timeSlot, onChange, disabled]
  );

  return (
    <div className={`time-slot-editor ${error ? "time-slot-editor-error" : ""}`}>
      <label className="time-slot-fullday">
        <input
          type="checkbox"
          checked={isFullDay}
          onChange={handleFullDayToggle}
          disabled={disabled}
        />
        <span>Full day</span>
      </label>

      {/* {!isFullDay && (
        <div className="time-slot-row"> */}
      {!isFullDay && (
        <div className="time-slot-timebox">
          <div className="time-slot-row">
          <div className="time-slot-field">
            <span className="time-slot-label">From</span>
            <div className="time-slot-pair">
              <select
                className="time-slot-select"
                value={timeSlot.start_hour}
                onChange={(e) => handleFieldChange("start_hour", e.target.value)}
                disabled={disabled}
                aria-label="Start hour"
              >
                {HOUR_OPTIONS_START.map((h) => (
                  <option key={h} value={h}>
                    {pad2(h)}
                  </option>
                ))}
              </select>
              <span className="time-slot-colon">:</span>
              <select
                className="time-slot-select"
                value={timeSlot.start_minute || 0}
                onChange={(e) => handleFieldChange("start_minute", e.target.value)}
                disabled={disabled}
                aria-label="Start minute"
              >
                {startMinuteOptions.map((m) => (
                  <option key={m} value={m}>
                    {pad2(m)}
                  </option>
                ))}
              </select>
            </div>
          </div>
          </div>

          <span className="time-slot-arrow" aria-hidden="true">
            →
          </span>

          <div className="time-slot-field">
            <span className="time-slot-label">To</span>
            <div className="time-slot-pair">
              <select
                className="time-slot-select"
                value={timeSlot.end_hour}
                onChange={(e) => handleFieldChange("end_hour", e.target.value)}
                disabled={disabled}
                aria-label="End hour"
              >
                {HOUR_OPTIONS_END.map((h) => (
                  <option key={h} value={h}>
                    {pad2(h)}
                  </option>
                ))}
              </select>
              <span className="time-slot-colon">:</span>
              <select
                className="time-slot-select"
                value={timeSlot.end_minute || 0}
                onChange={(e) => handleFieldChange("end_minute", e.target.value)}
                disabled={disabled}
                aria-label="End minute"
              >
                {endMinuteOptions.map((m) => (
                  <option key={m} value={m}>
                    {pad2(m)}
                  </option>
                ))}
              </select>
            </div>
          </div>
        </div>
      )}

      {error ? <div className="time-slot-error-text">{error}</div> : null}
    </div>
  );
}

TimeSlotEditor.propTypes = {
  timeSlot: PropTypes.shape({
    start_hour: PropTypes.number,
    start_minute: PropTypes.number,
    end_hour: PropTypes.number,
    end_minute: PropTypes.number,
  }),
  onChange: PropTypes.func.isRequired,
  error: PropTypes.string,
  disabled: PropTypes.bool,
};
