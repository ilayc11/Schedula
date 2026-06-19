// Validation helpers for DaySelector. Kept in a separate file so the
// component module satisfies react-refresh/only-export-components.

export function validateDays(days) {
  if (!Array.isArray(days) || days.length === 0) {
    return "Pick at least one day";
  }
  for (const d of days) {
    if (!Number.isInteger(d) || d < 1 || d > 6) {
      return `Invalid day: ${d}`;
    }
  }
  return null;
}
