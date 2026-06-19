// Validation helpers for TimeSlotEditor. Kept in a separate file so the
// component module satisfies react-refresh/only-export-components.

function pad2(n) {
  return String(n ?? 0).padStart(2, "0");
}

export function validateTimeSlot(timeSlot) {
  if (timeSlot === null || timeSlot === undefined) return null;
  if (typeof timeSlot !== "object") return "Invalid time slot";

  const sh = Number(timeSlot.start_hour);
  const eh = Number(timeSlot.end_hour);
  const sm = Number(timeSlot.start_minute || 0);
  const em = Number(timeSlot.end_minute || 0);

  if (!Number.isInteger(sh) || sh < 0 || sh > 23) return "start_hour must be 0..23";
  if (!Number.isInteger(eh) || eh < 0 || eh > 24) return "end_hour must be 0..24";
  if (!Number.isInteger(sm) || sm < 0 || sm > 59) return "start_minute must be 0..59";
  if (!Number.isInteger(em) || em < 0 || em > 59) return "end_minute must be 0..59";

  const startTotal = sh * 60 + sm;
  const endTotal = eh * 60 + em;
  if (startTotal >= endTotal) {
    return `Start (${pad2(sh)}:${pad2(sm)}) must be before end (${pad2(eh)}:${pad2(em)})`;
  }
  return null;
}
