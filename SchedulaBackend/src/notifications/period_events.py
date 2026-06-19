import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from uuid import uuid4

from src.config import settings
from src.rabbitmq.rabbitmq import rabbitmq
from src.repositories import lecturer_courses as lecturer_courses_repo
from src.repositories import schedule_queries as schedule_queries_repo
from src.repositories import schedules as schedules_repo
from src.repositories import semesters as semesters_repo
from src.repositories import period_notification_events as period_events_repo
from src.repositories import semester_period_state as period_state_repo

logger = logging.getLogger(__name__)

_DAY_NAMES = {
    1: "Sunday",
    2: "Monday",
    3: "Tuesday",
    4: "Wednesday",
    5: "Thursday",
    6: "Friday",
}


def _now_utc_date() -> date:
    return datetime.now(timezone.utc).date()


def _build_event_payload(
    *,
    semester_year: int,
    semester_number: int,
    period_type: str,
    transition_type: str,
    warning_hours: int | None = None,
    old_status: str | None = None,
    new_status: str | None = None,
    transition_date: date | None = None,
) -> dict:
    transition_date_value = transition_date.isoformat() if transition_date else _now_utc_date().isoformat()

    return {
        "event_type": "period_transition",
        "semester_year": semester_year,
        "semester_number": semester_number,
        "period_type": period_type,
        "transition_type": transition_type,
        "warning_hours": warning_hours,
        "transition_date": transition_date_value,
        "old_status": old_status,
        "new_status": new_status,
        "status": new_status,
    }


def _build_period_message(metadata: dict) -> tuple[str, str]:
    semester_label = f"{metadata['semester_year']}/{metadata['semester_number']}"
    period_type = metadata.get("period_type")
    transition_type = metadata.get("transition_type")

    if period_type == "status":
        old_status = metadata.get("old_status") or "unknown"
        new_status = metadata.get("new_status") or "unknown"
        title = "Semester Status Updated"
        body = (
            f"Semester {semester_label} status changed from {old_status} to {new_status}. "
            "Open Schedula for the latest timeline and actions."
        )
        return title, body

    period_label = "Constraint submission" if period_type == "constraint" else "Schedule changes"

    if transition_type == "start":
        title = f"{period_label} period started"
        body = (
            f"{period_label} period is now open for semester {semester_label}. "
            "Open Schedula to submit or review your updates."
        )
        return title, body

    if transition_type == "starting_soon":
        warning_hours = metadata.get("warning_hours") or 48
        title = f"{period_label} period starting soon"
        body = (
            f"{period_label} period for semester {semester_label} starts in about {warning_hours} hours. "
            "Get ready to act in Schedula when it opens."
        )
        return title, body

    if transition_type == "ending_soon":
        warning_hours = metadata.get("warning_hours") or 24
        title = f"{period_label} period ending soon"
        body = (
            f"{period_label} period for semester {semester_label} ends in about {warning_hours} hours. "
            "Please complete any remaining actions in Schedula."
        )
        return title, body

    if transition_type == "ended":
        title = f"{period_label} period ended"
        body = (
            f"{period_label} period has ended for semester {semester_label}. "
            "Further changes are now restricted based on semester policy."
        )
        return title, body

    return "Schedula Period Update", f"There is an update for semester {semester_label}."


async def _publish_period_notification(metadata: dict) -> bool:
    semester_year = int(metadata["semester_year"])
    semester_number = int(metadata["semester_number"])
    recipient_user_ids = await lecturer_courses_repo.list_unique_lecturer_ids_for_semester(
        semester_year,
        semester_number,
    )

    if not recipient_user_ids:
        logger.info(
            "No lecturer recipients found for period event %s on semester %s/%s",
            metadata.get("transition_type"),
            semester_year,
            semester_number,
        )
        return False

    title, body = _build_period_message(metadata)

    event = {
        "schema_version": "2.0",
        "message_type": "period_transition",
        "message_id": str(uuid4()),
        "recipient_user_ids": recipient_user_ids,
        "metadata": metadata,
        "payload": {
            "title": title,
            "body": body,
            "urls": [],
        },
    }

    await rabbitmq.publish(settings.notification_queue_name, event)
    logger.info(
        "Published period_transition notification for semester %s/%s to %d recipients",
        semester_year,
        semester_number,
        len(recipient_user_ids),
    )
    return True


async def _process_event_candidate(
    *,
    semester_year: int,
    semester_number: int,
    event_key: str,
    event_date: date,
    metadata: dict,
    source: str,
) -> None:
    row = await period_events_repo.reserve_event(
        semester_year=semester_year,
        semester_number=semester_number,
        event_key=event_key,
        event_date=event_date,
        payload=metadata,
        source=source,
    )

    if not row:
        return

    if row.get("published_at") is not None:
        return

    try:
        await _publish_period_notification(metadata)
        await period_events_repo.mark_published(int(row["event_id"]))
    except Exception:
        logger.exception(
            "Failed publishing period event key=%s for semester %s/%s",
            event_key,
            semester_year,
            semester_number,
        )


async def process_status_change_event(
    *,
    semester_year: int,
    semester_number: int,
    previous_status: str,
    current_status: str,
    source: str,
) -> None:
    if previous_status == current_status:
        return

    today = _now_utc_date()
    metadata = _build_event_payload(
        semester_year=semester_year,
        semester_number=semester_number,
        period_type="status",
        transition_type="changed",
        old_status=previous_status,
        new_status=current_status,
        transition_date=today,
    )
    await _process_event_candidate(
        semester_year=semester_year,
        semester_number=semester_number,
        event_key=f"status_changed_{previous_status}_to_{current_status}",
        event_date=today,
        metadata=metadata,
        source=source,
    )


def _format_time_value(value: Any) -> str:
    if isinstance(value, time):
        return value.strftime("%H:%M")
    if isinstance(value, datetime):
        return value.strftime("%H:%M")
    text = str(value or "")
    return text[:5] if len(text) >= 5 else text


def _format_session_line(session: dict) -> str:
    day_name = _DAY_NAMES.get(int(session.get("day_of_week", 0)), f"Day {session.get('day_of_week')}")
    course_name = session.get("course_name") or "Untitled course"
    start = _format_time_value(session.get("start_time"))
    end = _format_time_value(session.get("end_time"))
    group_number = session.get("group_number")
    suffix = f" (group {group_number})" if group_number is not None else ""
    return f"- {course_name}{suffix}: {day_name} {start}-{end}"


def _build_lecturer_schedule_body(
    *,
    semester_year: int,
    semester_number: int,
    sessions: list[dict],
    schedule_url: str,
) -> str:
    semester_label = f"{semester_year}/{semester_number}"
    if not sessions:
        return (
            f"The schedule changes period for semester {semester_label} has started, "
            "and you currently have no sessions assigned. "
            f"Review your schedule here: {schedule_url}"
        )

    lines = [_format_session_line(session) for session in sessions]
    return (
        f"The schedule changes period for semester {semester_label} has started. "
        "Your current sessions:\n"
        + "\n".join(lines)
        + f"\n\nReview your full schedule: {schedule_url}"
    )


async def _publish_change_start_schedule_snapshot_for_lecturer(
    *,
    lecturer_internal_id: int,
    schedule_id: int,
    semester_year: int,
    semester_number: int,
) -> None:
    sessions = await schedule_queries_repo.get_detailed_schedule(
        schedule_id=schedule_id,
        lecturer_internal_id=lecturer_internal_id,
    )

    base = settings.frontend_base_url.rstrip("/")
    schedule_url = f"{base}/schedules/{schedule_id}"

    title = f"Your schedule for {semester_year}/{semester_number}"
    body = _build_lecturer_schedule_body(
        semester_year=semester_year,
        semester_number=semester_number,
        sessions=sessions,
        schedule_url=schedule_url,
    )

    event = {
        "schema_version": "2.0",
        "message_type": "change_start_schedule_snapshot",
        "message_id": str(uuid4()),
        "recipient_user_ids": [int(lecturer_internal_id)],
        "metadata": {
            "event_type": "change_start_schedule_snapshot",
            "semester_year": int(semester_year),
            "semester_number": int(semester_number),
            "schedule_id": int(schedule_id),
            "lecturer_internal_id": int(lecturer_internal_id),
            "session_count": len(sessions),
        },
        "payload": {
            "title": title,
            "body": body,
            "urls": [schedule_url],
        },
    }

    await rabbitmq.publish(settings.notification_queue_name, event)


async def _process_change_start_schedule_snapshots(
    *,
    semester_year: int,
    semester_number: int,
    event_date: date,
    source: str,
) -> None:
    """Publish a personalised schedule snapshot to every lecturer in the semester.

    Idempotency is achieved through ``period_notification_events`` keyed on
    ``change_start_schedule_snapshot``: the whole fan-out runs at most once
    per ``(year, number, date)``. If the process crashes mid-fan-out the
    next invocation will retry and may send duplicates to lecturers that
    were already notified -- this matches the existing behaviour of
    ``_process_event_candidate`` for the broadcast event.
    """
    latest_schedule = await schedules_repo.get_latest_schedule_for_semester(
        semester_year, semester_number
    )
    if latest_schedule is None:
        logger.info(
            "change_start: no schedule exists yet for semester %s/%s, skipping snapshot fan-out",
            semester_year,
            semester_number,
        )
        return

    schedule_id = int(latest_schedule["schedule_id"])

    metadata = {
        "event_type": "change_start_schedule_snapshot",
        "semester_year": semester_year,
        "semester_number": semester_number,
        "schedule_id": schedule_id,
    }
    row = await period_events_repo.reserve_event(
        semester_year=semester_year,
        semester_number=semester_number,
        event_key="change_start_schedule_snapshot",
        event_date=event_date,
        payload=metadata,
        source=source,
    )
    if not row:
        return

    if row.get("published_at") is not None:
        return

    recipient_user_ids = await lecturer_courses_repo.list_unique_lecturer_ids_for_semester(
        semester_year, semester_number
    )
    if not recipient_user_ids:
        logger.info(
            "change_start: no lecturers found for semester %s/%s, marking snapshot fan-out as published",
            semester_year,
            semester_number,
        )
        await period_events_repo.mark_published(int(row["event_id"]))
        return

    for lecturer_internal_id in recipient_user_ids:
        try:
            await _publish_change_start_schedule_snapshot_for_lecturer(
                lecturer_internal_id=int(lecturer_internal_id),
                schedule_id=schedule_id,
                semester_year=semester_year,
                semester_number=semester_number,
            )
        except Exception:
            logger.exception(
                "Failed publishing change_start snapshot for lecturer %s in %s/%s",
                lecturer_internal_id,
                semester_year,
                semester_number,
            )

    await period_events_repo.mark_published(int(row["event_id"]))
    logger.info(
        "Published change_start schedule snapshot for %d lecturers in %s/%s (schedule_id=%s)",
        len(recipient_user_ids),
        semester_year,
        semester_number,
        schedule_id,
    )


async def process_semester_time_events(semester_data: dict, source: str) -> None:
    semester_year = int(semester_data["semester_year"])
    semester_number = int(semester_data["semester_number"])
    today = _now_utc_date()

    def _candidate(period_type: str, transition_type: str, event_key: str, warning_hours: int | None = None) -> tuple[str, dict]:
        return (
            event_key,
            _build_event_payload(
                semester_year=semester_year,
                semester_number=semester_number,
                period_type=period_type,
                transition_type=transition_type,
                warning_hours=warning_hours,
                transition_date=today,
            ),
        )

    candidates: list[tuple[str, dict]] = []

    constraint_start = semester_data["constraint_start_date"]
    constraint_end = semester_data["constraint_end_date"]
    change_start = semester_data["change_period_start"]
    change_end = semester_data["change_period_end"]

    if today == constraint_start - timedelta(days=2):
        candidates.append(_candidate("constraint", "starting_soon", "constraint_starting_48h", warning_hours=48))
    if today == constraint_start:
        candidates.append(_candidate("constraint", "start", "constraint_start"))
    if today == constraint_end - timedelta(days=2):
        candidates.append(_candidate("constraint", "ending_soon", "constraint_ending_48h", warning_hours=48))
    if today == constraint_end - timedelta(days=1):
        candidates.append(_candidate("constraint", "ending_soon", "constraint_ending_24h", warning_hours=24))
    if today == constraint_end + timedelta(days=1):
        candidates.append(_candidate("constraint", "ended", "constraint_ended"))

    if today == change_start - timedelta(days=2):
        candidates.append(_candidate("change", "starting_soon", "change_starting_48h", warning_hours=48))
    if today == change_start:
        candidates.append(_candidate("change", "start", "change_start"))
        # Fan out a personalised "your current schedule" message to every
        # lecturer in the semester. Tracked under its own idempotency key so
        # the fan-out can succeed/fail independently of the broadcast above.
        await _process_change_start_schedule_snapshots(
            semester_year=semester_year,
            semester_number=semester_number,
            event_date=today,
            source=source,
        )
    if today == change_end - timedelta(days=2):
        candidates.append(_candidate("change", "ending_soon", "change_ending_48h", warning_hours=48))
    if today == change_end - timedelta(days=1):
        candidates.append(_candidate("change", "ending_soon", "change_ending_24h", warning_hours=24))
    if today == change_end + timedelta(days=1):
        candidates.append(_candidate("change", "ended", "change_ended"))

    for event_key, metadata in candidates:
        await _process_event_candidate(
            semester_year=semester_year,
            semester_number=semester_number,
            event_key=event_key,
            event_date=today,
            metadata=metadata,
            source=source,
        )


async def process_semester_status_from_state(semester_data: dict, source: str) -> None:
    semester_year = int(semester_data["semester_year"])
    semester_number = int(semester_data["semester_number"])
    current_status = str(semester_data["status"])

    state = await period_state_repo.get_status_state(semester_year, semester_number)
    if state is None:
        await period_state_repo.upsert_status_state(semester_year, semester_number, current_status)
        return

    previous_status = str(state["last_seen_status"])
    if previous_status == current_status:
        return

    await process_status_change_event(
        semester_year=semester_year,
        semester_number=semester_number,
        previous_status=previous_status,
        current_status=current_status,
        source=source,
    )
    await period_state_repo.upsert_status_state(semester_year, semester_number, current_status)


async def run_period_transition_checks(source: str = "scheduler") -> None:
    semesters = await semesters_repo.list_semesters()
    for semester in semesters:
        await process_semester_time_events(semester, source=source)
        await process_semester_status_from_state(semester, source=source)


async def process_semester_update_transition(previous: dict, current: dict) -> None:
    semester_year = int(current["semester_year"])
    semester_number = int(current["semester_number"])

    previous_status = str(previous["status"])
    current_status = str(current["status"])
    if previous_status != current_status:
        await process_status_change_event(
            semester_year=semester_year,
            semester_number=semester_number,
            previous_status=previous_status,
            current_status=current_status,
            source="secretary_update",
        )
        await period_state_repo.upsert_status_state(semester_year, semester_number, current_status)

    # If a secretary updates date boundaries to today's trigger point, notify immediately.
    await process_semester_time_events(current, source="secretary_update")
