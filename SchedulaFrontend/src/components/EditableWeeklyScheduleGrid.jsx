import "./WeeklyScheduleGrid.css";

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
const HOUR_SLOT_PX = 90;
const PX_PER_MIN = HOUR_SLOT_PX / 60;

function toMinutes(hhmm) {
  const [h, m] = String(hhmm).slice(0, 5).split(":").map(Number);
  return h * 60 + m;
}

function formatTime(hhmm) {
  return String(hhmm).slice(0, 5);
}

function minutesToTime(totalMinutes) {
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}`;
}

function getSessionDurationInMinutes(session) {
  return toMinutes(session.end_time) - toMinutes(session.start_time);
}

export default function EditableWeeklyScheduleGrid({
  sessions,
  showLecturer = false,
  setDraftSessions,
  setHasUnsavedChanges,
}) {
  const dayBuckets = new Map();
  DAYS.forEach((day) => dayBuckets.set(day.key, []));

  for (const session of sessions || []) {
    const dayKey = DAYS.find((day) => day.backendDay === session.day_of_week)?.key;
    if (!dayKey) continue;
    dayBuckets.get(dayKey).push(session);
  }

  const totalHours = END_HOUR - START_HOUR + 1;
  const gridHeight = totalHours * HOUR_SLOT_PX;

  const hours = [];
  for (let hour = START_HOUR; hour <= END_HOUR; hour += 1) {
    hours.push(hour);
  }

  const handleDragStart = (event, session) => {
    event.dataTransfer.setData("sessionId", String(session.session_id));
  };

  const handleDragOver = (event) => {
    event.preventDefault();
  };

  const handleDrop = (event, targetDay, targetHour) => {
    event.preventDefault();

    const draggedSessionId = event.dataTransfer.getData("sessionId");
    if (!draggedSessionId) return;

    setDraftSessions((prevSessions) =>
      (prevSessions || []).map((session) => {
        if (String(session.session_id) !== String(draggedSessionId)) {
          return session;
        }

        const duration = getSessionDurationInMinutes(session);
        const newStartMinutes = targetHour * 60;
        const newEndMinutes = newStartMinutes + duration;

        return {
          ...session,
          day_of_week: targetDay,
          start_time: minutesToTime(newStartMinutes),
          end_time: minutesToTime(newEndMinutes),
        };
      })
    );

    setHasUnsavedChanges(true);
  };

  return (
    <div className="week-wrap">
      <div className="week-grid">
        <div className="corner" />

        {DAYS.map((day) => (
          <div key={day.key} className="day-header">
            {day.label}
          </div>
        ))}

        <div className="time-col">
          {hours.map((hour) => (
            <div key={hour} className="time-slot" style={{ height: HOUR_SLOT_PX }}>
              {String(hour).padStart(2, "0")}:00
            </div>
          ))}
        </div>

        {DAYS.map((day) => (
          <div key={day.key} className="day-col" style={{ height: gridHeight }}>
            <div className="day-lines" style={{ height: gridHeight }}>
              {hours.map((hour) => (
                <div
                  key={hour}
                  className="hour-line"
                  style={{ top: (hour - START_HOUR) * 60 * PX_PER_MIN }}
                />
              ))}
            </div>

            {hours.slice(0, -1).map((hour) => (
              <div
                key={`${day.key}-${hour}`}
                className="drop-slot"
                style={{
                  position: "absolute",
                  top: (hour - START_HOUR) * HOUR_SLOT_PX,
                  left: 0,
                  right: 0,
                  height: HOUR_SLOT_PX,
                  zIndex: 1,
                }}
                onDragOver={handleDragOver}
                onDrop={(event) => handleDrop(event, day.backendDay, hour)}
              />
            ))}

            {(dayBuckets.get(day.key) || []).map((session) => {
              const start = toMinutes(session.start_time);
              const end = toMinutes(session.end_time);

              const top = Math.max(0, (start - START_HOUR * 60) * PX_PER_MIN);
              const height = Math.max(72, (end - start) * PX_PER_MIN);

              return (
                <div
                  key={
                    session.session_id ??
                    `${session.course_number}-${session.start_time}-${session.day_of_week}`
                  }
                  className="event"
                  style={{ top, height, zIndex: 3, cursor: "grab" }}
                  title={`${session.course_name} (${session.course_number})`}
                  draggable
                  onDragStart={(event) => handleDragStart(event, session)}
                >
                  <div className="event-title">{session.course_name}</div>

                  {showLecturer && session.lecturer_name && (
                    <div className="event-lecturer">{session.lecturer_name}</div>
                  )}

                  <div className="event-meta">
                    {session.course_number} · Group {session.group_number}
                  </div>

                  <div className="event-time">
                    {formatTime(session.start_time)} – {formatTime(session.end_time)}
                  </div>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}