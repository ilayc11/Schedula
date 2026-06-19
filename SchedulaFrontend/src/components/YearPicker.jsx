// src/components/YearPicker.jsx
//
// Shared year picker used across the app. It's a react-datepicker in
// year-only mode (the same control the Schedule Manager / Fairness pages use):
// the user picks a year from a calendar-style popup, and only the year value
// is surfaced to the caller.
//
// Usage:
//   <YearPicker year={year} onChange={(y) => setYear(y)} disabled={isLoading} />

import PropTypes from "prop-types";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";

const MIN_YEAR = 2000;
const MAX_YEAR = 2100;

export default function YearPicker({
  year,
  onChange,
  disabled = false,
  className = "search-input",
}) {
  const numericYear = Number(year);
  const selected = Number.isFinite(numericYear)
    ? new Date(numericYear, 0, 1)
    : null;

  return (
    <DatePicker
      selected={selected}
      onChange={(date) => {
        if (!date) return;
        onChange(date.getFullYear());
      }}
      showYearPicker
      dateFormat="yyyy"
      minDate={new Date(MIN_YEAR, 0, 1)}
      maxDate={new Date(MAX_YEAR, 0, 1)}
      className={className}
      disabled={disabled}
    />
  );
}

YearPicker.propTypes = {
  year: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  onChange: PropTypes.func.isRequired,
  disabled: PropTypes.bool,
  className: PropTypes.string,
};
