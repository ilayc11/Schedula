// src/components/WeeklyScheduleGrid.jsx
import { useState } from "react";
import "./WeeklyScheduleGrid.css";
import CourseDetailsModal from "./CourseDetailsModal.jsx";

const DAYS = [
  { key: "SUN", label: "SUN", backendDay: 1 }, 
  { key: "MON", label: "MON", backendDay: 2 },
  { key: "TUE", label: "TUE", backendDay: 3 },
  { key: "WED", label: "WED", backendDay: 4 },
  { key: "THU", label: "THU", backendDay: 5 },
  { key: "FRI", label: "FRI", backendDay: 6 },
];

const START_HOUR = 8;
const END_HOUR = 20;
// const PX_PER_MIN = 1;
const HOUR_SLOT_PX = 90;
const PX_PER_MIN = HOUR_SLOT_PX / 60;

function toMinutes(hhmm) {
  const [h, m] = String(hhmm).split(":").map(Number);
  return h * 60 + m;
}

function formatTime(hhmm) {
  return String(hhmm);
}

// Lay sessions out side-by-side when they overlap in time.
// Returns each session annotated with { column, columns } where `columns`
// is the number of side-by-side lanes needed for its overlap group.
function assignColumns(daySessions) {
  const sorted = [...daySessions]
    .map((session) => ({
      session,
      start: toMinutes(session.start_time),
      end: toMinutes(session.end_time),
    }))
    .sort((a, b) => a.start - b.start || a.end - b.end);

  const placed = [];
  let group = [];
  let groupMaxEnd = -Infinity;

  // Once a group of mutually overlapping events ends, every event in it
  // shares the same column count so their widths line up.
  const flushGroup = () => {
    const columnsUsed = group.reduce((max, item) => Math.max(max, item.column + 1), 0);
    group.forEach((item) => {
      item.columns = columnsUsed;
    });
    group = [];
    groupMaxEnd = -Infinity;
  };

  for (const item of sorted) {
    if (group.length > 0 && item.start >= groupMaxEnd) {
      flushGroup();
    }

    // Find the first column free at this event's start time.
    const activeColumns = new Set(
      group.filter((other) => other.end > item.start).map((other) => other.column)
    );
    let column = 0;
    while (activeColumns.has(column)) column += 1;

    item.column = column;
    group.push(item);
    groupMaxEnd = Math.max(groupMaxEnd, item.end);
    placed.push(item);
  }

  if (group.length > 0) flushGroup();

  return placed;
}

function WeeklyScheduleGrid({ sessions, showLecturer = false }) {
  const [selectedSession, setSelectedSession] = useState(null);

  const dayBuckets = new Map();
  DAYS.forEach((d) => dayBuckets.set(d.key, []));

  for (const s of sessions || []) {
    const dayKey =
      DAYS.find((d) => d.backendDay === s.day_of_week)?.key || null;
    if (!dayKey) continue;
    dayBuckets.get(dayKey).push(s);
  }

  const totalHours = END_HOUR - START_HOUR + 1; // +1 to include the end hour visually
  const gridHeight = totalHours * HOUR_SLOT_PX;

  const hours = [];
  for (let h = START_HOUR; h <= END_HOUR; h += 1) {
    hours.push(h);
  }

  return (
    <div className="week-wrap">
      <div className="week-grid">
        <div className="corner" />

        {DAYS.map((d) => (
          <div key={d.key} className="day-header">
            {d.label}
          </div>
        ))}

        <div className="time-col">
          {hours.map((h) => (
            <div key={h} className="time-slot" style={{ height: HOUR_SLOT_PX }}>
              {String(h).padStart(2, "0")}:00
            </div>
          ))}
        </div>

        {DAYS.map((d) => {
          const laidOut = assignColumns(dayBuckets.get(d.key) || []);

          return (
            <div key={d.key} className="day-col" style={{ height: gridHeight }}>
              <div className="day-lines" style={{ height: gridHeight }}>
                {hours.map((h) => (
                  <div key={h} className="hour-line" style={{ top: (h - START_HOUR) * 60 * PX_PER_MIN }} />
                ))}
              </div>

              {laidOut.map(({ session: s, start, end, column, columns }) => {
                const top = Math.max(0, (start - START_HOUR * 60) * PX_PER_MIN);
                const height = Math.max(72, (end - start) * PX_PER_MIN);

                // Split the column width across the overlapping lanes.
                const widthPct = 100 / columns;
                const leftPct = column * widthPct;

                return (
                  <div
                    key={s.session_id ?? `${s.course_number}-${s.start_time}-${s.day_of_week}`}
                    className={`event event--clickable${columns > 1 ? " event--narrow" : ""}`}
                    style={{
                      top,
                      height,
                      left: `calc(${leftPct}% + 4px)`,
                      width: `calc(${widthPct}% - 8px)`,
                    }}
                    title={`${s.course_name} (${s.course_number}) · ${formatTime(s.start_time)}–${formatTime(s.end_time)}`}
                    onClick={() => setSelectedSession(s)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        setSelectedSession(s);
                      }
                    }}
                  >
                    <div className="event-title">{s.course_name}</div>
                    {showLecturer && s.lecturer_name && (
                      <div className="event-lecturer">{s.lecturer_name}</div>
                    )}
                    <div className="event-meta">
                      {s.course_number} · Group {s.group_number}
                    </div>
                    <div className="event-time">
                      {formatTime(s.start_time)} – {formatTime(s.end_time)}
                    </div>
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>

      <CourseDetailsModal
        session={selectedSession}
        onClose={() => setSelectedSession(null)}
      />
    </div>
  );
}

export default WeeklyScheduleGrid;
