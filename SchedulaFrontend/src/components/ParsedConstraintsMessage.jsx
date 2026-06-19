import { useMemo, useState } from "react";
import PropTypes from "prop-types";
import "./ParsedConstraintsMessage.css";
import Tooltip from "./Tooltip.jsx";
import { tooltipForType, tooltipForDay, tooltipForTime } from "./tooltipTexts.js";

const DAY_INDEX_TO_NAME = {
  1: "SUNDAY",
  2: "MONDAY",
  3: "TUESDAY",
  4: "WEDNESDAY",
  5: "THURSDAY",
  6: "FRIDAY",
};

const DAY_NAME_TO_INDEX = {
  SUNDAY: 1,
  MONDAY: 2,
  TUESDAY: 3,
  WEDNESDAY: 4,
  THURSDAY: 5,
  FRIDAY: 6,
};

const DAY_OPTIONS = ["", "SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY"];
const TYPE_OPTIONS = ["BLOCK", "PREFERENCE"];

// Working-hours windows enforced in the UI (mirrors the solver):
// all days open at 08:00; Sun–Thu close at 20:00, Friday closes at 15:00.
// Saturday is not schedulable, so it is absent from DAY_OPTIONS.
const DEFAULT_DAY_BOUNDS = { min: "08:00", max: "20:00" };
const DAY_BOUNDS = {
  FRIDAY: { min: "08:00", max: "15:00" },
};

function boundsForDay(day) {
  return DAY_BOUNDS[String(day || "").toUpperCase()] || DEFAULT_DAY_BOUNDS;
}

// "HH:MM" strings compare correctly lexicographically because they are zero-padded.
function clampTime(value, { min, max }) {
  if (!value) return value;
  if (value < min) return min;
  if (value > max) return max;
  return value;
}

function toMinutes(t) {
  const [h, m] = String(t).split(":").map(Number);
  return h * 60 + m;
}

// Build selectable time options within [min, max] at a fixed step (default 30m).
// Any off-grid value (e.g. an odd time from the LLM) is merged in so it is not lost.
function timeOptions(min, max, value, stepMinutes = 30) {
  const start = toMinutes(min);
  const end = toMinutes(max);
  const opts = [];
  for (let m = start; m <= end; m += stepMinutes) {
    opts.push(`${pad2(Math.floor(m / 60))}:${pad2(m % 60)}`);
  }
  if (value && value >= min && value <= max && !opts.includes(value)) {
    opts.push(value);
    opts.sort();
  }
  return opts;
}

// Priority is not shown to lecturers; it is derived from the rule type.
// A BLOCK is a hard constraint, a PREFERENCE is soft.
function priorityForType(type) {
  return String(type || "").toUpperCase() === "PREFERENCE" ? "soft" : "hard";
}

function pad2(n) {
  return String(n).padStart(2, "0");
}

// Editor-friendly: a present hour with a missing minute defaults to :00
function toTimeSafe(h, m) {
  if (h == null) return "";
  return `${pad2(h)}:${pad2(m ?? 0)}`;
}

function timeToParts(t) {
  if (!t) return { hour: null, minute: null };
  const [h, m] = String(t).split(":");
  const hour = Number(h);
  const minute = Number(m ?? 0);
  return {
    hour: Number.isFinite(hour) ? hour : null,
    minute: Number.isFinite(minute) ? minute : 0,
  };
}

function normalizeDay(d) {
  if (typeof d === "number") return DAY_INDEX_TO_NAME[d] ?? String(d);

  if (typeof d === "string") {
    const upper = d.trim().toUpperCase();
    if (upper in DAY_INDEX_TO_NAME) return DAY_INDEX_TO_NAME[Number(upper)];
    return upper;
  }

  return String(d);
}

function normalizeStructuredRules(structuredRules) {
  if (!structuredRules) return [];

  // If already normalized: [{type, day, from, to}, ...]
  if (
    Array.isArray(structuredRules) &&
    structuredRules.every((r) => r && typeof r === "object" && "type" in r)
  ) {
    return structuredRules.map((r) => ({
      type: String(r.type || "").toUpperCase(),
      day: String(r.day || "").toUpperCase(),
      from: String(r.from || ""),
      to: String(r.to || ""),
    }));
  }

  // LLM format: { atomic_constraints: [...] }
  const atomic = Array.isArray(structuredRules.atomic_constraints)
    ? structuredRules.atomic_constraints
    : [];

  const normalized = [];

  for (const c of atomic) {
    const type = String(c?.type || "").toUpperCase();

    const days = Array.isArray(c?.days) ? c.days : [];
    const slot = c?.time_slot || {};

    const from = toTimeSafe(slot.start_hour, slot.start_minute);
    const to = toTimeSafe(slot.end_hour, slot.end_minute);

    // If days list is empty, still keep something meaningful
    if (days.length === 0) {
      normalized.push({
        type: type || "BLOCK",
        day: "",
        from,
        to,
      });
      continue;
    }

    for (const d of days) {
      normalized.push({
        type: type || "BLOCK",
        day: normalizeDay(d),
        from,
        to,
      });
    }
  }

  return normalized;
}

// Convert the editable normalized rows back into the LLM/DB structured_rules shape
function rulesToStructured(rules) {
  const atomic_constraints = (rules || []).map((r) => {
    const dayName = String(r.day || "").toUpperCase();
    const dayIdx = DAY_NAME_TO_INDEX[dayName];
    const bounds = boundsForDay(dayName);

    const from = timeToParts(clampTime(r.from, bounds));
    const to = timeToParts(clampTime(r.to, bounds));

    const hasTime = from.hour != null || to.hour != null;
    const time_slot = hasTime
      ? {
          start_hour: from.hour,
          start_minute: from.minute ?? 0,
          end_hour: to.hour,
          end_minute: to.minute ?? 0,
        }
      : null;

    return {
      type: String(r.type || "block").toLowerCase(),
      days: dayIdx ? [dayIdx] : [],
      time_slot,
      priority: priorityForType(r.type),
    };
  });

  return { atomic_constraints };
}

function canEditRules(structuredRules) {
  if (!structuredRules) return false;
  if (typeof structuredRules === "string") return false;
  return normalizeStructuredRules(structuredRules).length >= 0;
}

function formatRulesToLines(structuredRules) {
  if (!structuredRules) return ["(No rules returned)"];

  if (typeof structuredRules === "string") {
    const lines = structuredRules
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);
    return lines.length ? lines : ["(No rules returned)"];
  }

  const normalized = normalizeStructuredRules(structuredRules);

  if (normalized.length === 0) {
    return ["(No structured rules parsed)"];
  }

  try {
    const pretty = JSON.stringify(structuredRules, null, 2);
    const asLines = pretty.split("\n");
    if (asLines.length > 60) {
      return [
        "(Rules returned, but could not normalize them cleanly.)",
        "(Open console for full JSON if needed.)",
      ];
    }
    return asLines;
  } catch {
    return [String(structuredRules)];
  }
}

function emptyRule() {
  return { type: "BLOCK", day: "", from: "", to: "" };
}

function ParsedConstraintsMessage({
  structuredRules,
  disabled,
  onApprove,
  onReject,
  title = "This is how I understood your constraints:",
  approveText = "approve",
  rejectText = "reject",
}) {
  // Editable rows seeded from the parsed LLM response. This lives in the
  // component so lecturers can add/edit/delete rules before saving.
  const [rules, setRules] = useState(() => normalizeStructuredRules(structuredRules));
  const [isEditing, setIsEditing] = useState(false);

  const lines = useMemo(() => formatRulesToLines(structuredRules), [structuredRules]);
  const editable = canEditRules(structuredRules) && !disabled;

  // A row is invalid when both times are set and start is not before end.
  function isRowInvalid(rule) {
    return Boolean(rule.from && rule.to && rule.from >= rule.to);
  }

  const hasInvalidRow = useMemo(() => rules.some(isRowInvalid), [rules]);

  function updateRule(idx, field, value) {
    setRules((prev) => {
      const copy = [...prev];
      const next = { ...copy[idx], [field]: value };

      // Keep times within the working-hours window for the (possibly new) day.
      const bounds = boundsForDay(field === "day" ? value : next.day);
      if (next.from) next.from = clampTime(next.from, bounds);
      if (next.to) next.to = clampTime(next.to, bounds);

      copy[idx] = next;
      return copy;
    });
  }

  function deleteRule(idx) {
    setRules((prev) => prev.filter((_, i) => i !== idx));
  }

  function addRule() {
    setRules((prev) => [...prev, emptyRule()]);
  }

  function handleApprove() {
    // Always hand back the (possibly edited) rules in DB shape.
    onApprove(rulesToStructured(rules));
  }

  return (
    <div className="pcm">
      <div className="pcm-title">{title}</div>

      <div className="pcm-preview" aria-label="Parsed constraints preview">
        {isEditing ? (
          <div className="pcm-edit-list">
            {rules.length === 0 ? (
              <p className="pcm-empty">No rules yet. Add one below.</p>
            ) : (
              rules.map((rule, idx) => {
                const bounds = boundsForDay(rule.day);
                const rowInvalid = isRowInvalid(rule);
                return (
                <div key={idx} className={`pcm-edit-row${rowInvalid ? " pcm-edit-row-invalid" : ""}`}>
                  <select
                    className="pcm-field pcm-field-type"
                    value={TYPE_OPTIONS.includes(rule.type) ? rule.type : "BLOCK"}
                    onChange={(e) => updateRule(idx, "type", e.target.value)}
                    aria-label="Rule type"
                  >
                    {TYPE_OPTIONS.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>

                  <select
                    className="pcm-field pcm-field-day"
                    value={DAY_OPTIONS.includes(rule.day) ? rule.day : ""}
                    onChange={(e) => updateRule(idx, "day", e.target.value)}
                    aria-label="Day"
                  >
                    {DAY_OPTIONS.map((d) => (
                      <option key={d || "ANY"} value={d}>
                        {d || "ANY DAY"}
                      </option>
                    ))}
                  </select>

                  <div className="pcm-time-field">
                    <label className="pcm-time-label">Start</label>
                    <select
                      className={`pcm-field pcm-field-time${rowInvalid ? " pcm-field-error" : ""}`}
                      value={rule.from || ""}
                      onChange={(e) => updateRule(idx, "from", e.target.value)}
                      aria-label="Start time"
                      aria-invalid={rowInvalid}
                    >
                      <option value="">All day</option>
                      {timeOptions(bounds.min, bounds.max, rule.from).map((t) => (
                        <option key={t} value={t} disabled={Boolean(rule.to) && t >= rule.to}>
                          {t}
                        </option>
                      ))}
                    </select>
                  </div>
                  <span className="pcm-divider pcm-time-dash">–</span>
                  <div className="pcm-time-field">
                    <label className="pcm-time-label">End</label>
                    <select
                      className={`pcm-field pcm-field-time${rowInvalid ? " pcm-field-error" : ""}`}
                      value={rule.to || ""}
                      onChange={(e) => updateRule(idx, "to", e.target.value)}
                      aria-label="End time"
                      aria-invalid={rowInvalid}
                    >
                      <option value="">All day</option>
                      {timeOptions(bounds.min, bounds.max, rule.to).map((t) => (
                        <option key={t} value={t} disabled={Boolean(rule.from) && t <= rule.from}>
                          {t}
                        </option>
                      ))}
                    </select>
                  </div>

                  <span className="pcm-window-note">{`${bounds.min}–${bounds.max}`}</span>

                  <button
                    type="button"
                    className="pcm-row-delete"
                    onClick={() => deleteRule(idx)}
                    aria-label="Delete rule"
                    title="Delete rule"
                  >
                    ✕
                  </button>

                  {rowInvalid && (
                    <span className="pcm-row-error">Start time must be before end time.</span>
                  )}
                </div>
                );
              })
            )}

            <button type="button" className="pcm-add" onClick={addRule}>
              + Add rule
            </button>
          </div>
        ) : rules.length > 0 ? (
          rules.map((rule, idx) => {
            const type = rule.type || "RULE";
            const day = rule.day || "ANY_DAY";
            const from = rule.from || "";
            const to = rule.to || "";

            const typeTip = tooltipForType(type);
            const dayTip = tooltipForDay(day);
            const timeTip = tooltipForTime(from, to);

            const timeLabel =
              from && to ? `${from} - ${to}` : from ? `from ${from}` : to ? `until ${to}` : "all day";

            return (
              <div key={idx} className="pcm-line-wrap">
                <span className="pcm-bullet">•</span>

                <Tooltip text={typeTip}>
                  <span className="pcm-chip pcm-chip-type">{type}</span>
                </Tooltip>

                <span className="pcm-divider">|</span>

                <Tooltip text={dayTip}>
                  <span className="pcm-chip pcm-chip-day">{day}</span>
                </Tooltip>

                <span className="pcm-divider">|</span>

                <Tooltip text={timeTip}>
                  <span className="pcm-chip pcm-chip-time">{timeLabel}</span>
                </Tooltip>
              </div>
            );
          })
        ) : (
          lines.map((line, idx) => (
            <pre key={idx} className="pcm-line">{line}</pre>
          ))
        )}
      </div>

      <div className="pcm-actions">
        {editable && (
          <button
            type="button"
            className="pcm-btn pcm-edit"
            onClick={() => setIsEditing((v) => !v)}
            disabled={disabled}
          >
            {isEditing ? "Done editing" : "Edit"}
          </button>
        )}

        <button
          type="button"
          className="pcm-btn pcm-approve"
          onClick={handleApprove}
          disabled={disabled || rules.length === 0 || hasInvalidRow}
        >
          {approveText}
        </button>

        <button
          type="button"
          className="pcm-btn pcm-reject"
          onClick={onReject}
          disabled={disabled}
        >
          {rejectText}
        </button>
      </div>

      <div className="pcm-hint">
        {hasInvalidRow
          ? "Fix the highlighted rows: start time must be before end time."
          : isEditing
          ? "Adjust, add, or remove rules, then click approve to save."
          : "Click Edit to adjust the rules, or reject and rephrase in the chat."}
      </div>
    </div>
  );
}

ParsedConstraintsMessage.propTypes = {
  structuredRules: PropTypes.any,
  disabled: PropTypes.bool,
  onApprove: PropTypes.func.isRequired,
  onReject: PropTypes.func.isRequired,
  title: PropTypes.string,
  approveText: PropTypes.string,
  rejectText: PropTypes.string,
};

export default ParsedConstraintsMessage;
