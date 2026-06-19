"""Notification publishers for lecturer-facing events.

These helpers wrap ``rabbitmq.publish(settings.notification_queue_name, ...)``
with the typed envelope shape consumed by ``notification_service``
(``schema_version="2.0"``, ``message_type``, ``recipient_user_ids``,
``metadata``, ``payload={title, body, urls}``).

Each helper is best-effort: failures are logged but never propagated, so the
HTTP route that produced the underlying domain change always returns its
real result to the caller.
"""

from __future__ import annotations

import logging
from typing import Iterable, Sequence
from uuid import uuid4

from src.config import settings
from src.rabbitmq.rabbitmq import rabbitmq
from src.repositories import lecturer_courses as lecturer_courses_repo

logger = logging.getLogger(__name__)


def _schedule_url(schedule_id: int) -> str:
    base = settings.frontend_base_url.rstrip("/")
    return f"{base}/schedules/{schedule_id}"


def _constraint_url(constraint_id: int) -> str:
    base = settings.frontend_base_url.rstrip("/")
    return f"{base}/constraints/{constraint_id}"


def _build_event(
    *,
    message_type: str,
    recipient_user_ids: Sequence[int],
    metadata: dict,
    title: str,
    body: str,
    urls: Iterable[str] = (),
) -> dict:
    return {
        "schema_version": "2.0",
        "message_type": message_type,
        "message_id": str(uuid4()),
        "recipient_user_ids": list(recipient_user_ids),
        "metadata": metadata,
        "payload": {
            "title": title,
            "body": body,
            "urls": list(urls),
        },
    }


async def _safe_publish(event: dict, *, log_context: str) -> bool:
    try:
        await rabbitmq.publish(settings.notification_queue_name, event)
        return True
    except Exception:
        logger.exception("Failed publishing lecturer notification (%s)", log_context)
        return False


async def publish_constraint_saved_by_lecturer(
    *,
    constraint_id: int,
    lecturer_internal_id: int,
    semester_year: int,
    semester_number: int,
) -> bool:
    """Confirm to the lecturer that their constraint has been saved successfully."""
    semester_label = f"{semester_year}/{semester_number}"
    title = "Constraint saved"
    body = (
        f"Your constraint for semester {semester_label} has been saved successfully. "
        "You can review or edit it any time in Schedula."
    )
    event = _build_event(
        message_type="lecturer_constraint_saved",
        recipient_user_ids=[lecturer_internal_id],
        metadata={
            "event_type": "lecturer_constraint_saved",
            "constraint_id": int(constraint_id),
            "semester_year": int(semester_year),
            "semester_number": int(semester_number),
        },
        title=title,
        body=body,
        urls=[_constraint_url(constraint_id)],
    )
    return await _safe_publish(
        event,
        log_context=f"constraint_saved constraint_id={constraint_id}",
    )


async def publish_constraint_edited_by_secretary(
    *,
    constraint_id: int,
    lecturer_internal_id: int,
    semester_year: int,
    semester_number: int,
) -> bool:
    """Tell the lecturer that the secretary edited their constraint."""
    semester_label = f"{semester_year}/{semester_number}"
    title = "Your constraint was updated by the secretary"
    body = (
        f"The secretary edited your constraint for semester {semester_label}. "
        "Open Schedula to review the change."
    )
    event = _build_event(
        message_type="lecturer_constraint_edited_by_secretary",
        recipient_user_ids=[lecturer_internal_id],
        metadata={
            "event_type": "lecturer_constraint_edited_by_secretary",
            "constraint_id": int(constraint_id),
            "semester_year": int(semester_year),
            "semester_number": int(semester_number),
        },
        title=title,
        body=body,
        urls=[_constraint_url(constraint_id)],
    )
    return await _safe_publish(
        event,
        log_context=f"secretary_edit constraint_id={constraint_id}",
    )


async def publish_schedule_published(
    *,
    schedule_id: int,
    semester_year: int,
    semester_number: int,
) -> bool:
    """Notify every lecturer in the semester that the schedule was officially published."""
    semester_label = f"{semester_year}/{semester_number}"
    recipient_user_ids = await lecturer_courses_repo.list_unique_lecturer_ids_for_semester(
        semester_year,
        semester_number,
    )
    if not recipient_user_ids:
        logger.info(
            "schedule_published: no lecturer recipients for semester %s, skipping",
            semester_label,
        )
        return False

    title = "Schedule published"
    body = (
        f"The schedule for semester {semester_label} has been officially published. "
        "Open Schedula to view your sessions."
    )
    event = _build_event(
        message_type="schedule_published",
        recipient_user_ids=recipient_user_ids,
        metadata={
            "event_type": "schedule_published",
            "schedule_id": int(schedule_id),
            "semester_year": int(semester_year),
            "semester_number": int(semester_number),
        },
        title=title,
        body=body,
        urls=[_schedule_url(schedule_id)],
    )
    return await _safe_publish(
        event,
        log_context=f"schedule_published schedule_id={schedule_id}",
    )
