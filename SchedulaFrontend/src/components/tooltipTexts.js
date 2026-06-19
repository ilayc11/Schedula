export function tooltipForType(type) {
  const t = String(type || "").toUpperCase();

  if (t === "BLOCK") {
    return "BLOCK means: this time window is off-limits. The scheduler will not place a class here.";
  }

  if (t === "PREFERENCE") {
    return "PREFERENCE means: the scheduler will try to avoid this window, but it may still schedule here if needed.";
  }

  return "";
}

export function tooltipForDay(day) {
  const d = String(day || "").toUpperCase();
  if (!d || d === "ANY_DAY") {
    return "Day is not specific here, this rule may apply more generally.";
  }
  return `This rule applies on ${d}.`;
}

export function tooltipForTime(from, to) {
  const hasFrom = Boolean(from);
  const hasTo = Boolean(to);

  if (hasFrom && hasTo) {
    return `Time window: ${from} to ${to}. The scheduler will avoid placing a class inside this window.`;
  }
  if (hasFrom) {
    return `From ${from} and onward. The scheduler will avoid placing a class starting at this time.`;
  }
  if (hasTo) {
    return `Until ${to}. The scheduler will avoid placing a class before this time.`;
  }
  return "All day. No specific hours were provided for this rule.";
}
