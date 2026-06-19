"""Unit tests for ``src.notifications.lecturer_events``."""

from __future__ import annotations

import pytest

from src.config import settings
from src.notifications import lecturer_events
from src.repositories import lecturer_courses as lecturer_courses_repo


async def test_publish_constraint_saved_by_lecturer_emits_typed_envelope(
    captured_publishes,
) -> None:
    ok = await lecturer_events.publish_constraint_saved_by_lecturer(
        constraint_id=88,
        lecturer_internal_id=42,
        semester_year=2027,
        semester_number=1,
    )

    assert ok is True
    queue_messages = captured_publishes.messages_for(settings.notification_queue_name)
    assert len(queue_messages) == 1

    event = queue_messages[0]
    assert event["schema_version"] == "2.0"
    assert event["message_type"] == "lecturer_constraint_saved"
    assert event["recipient_user_ids"] == [42]
    assert event["metadata"]["constraint_id"] == 88
    assert event["metadata"]["semester_year"] == 2027
    assert event["metadata"]["semester_number"] == 1
    assert event["payload"]["title"]
    assert "2027/1" in event["payload"]["body"]
    assert event["payload"]["urls"], "URL list must include the constraint link"


async def test_publish_constraint_edited_by_secretary_targets_only_constraint_owner(
    captured_publishes,
) -> None:
    ok = await lecturer_events.publish_constraint_edited_by_secretary(
        constraint_id=99,
        lecturer_internal_id=7,
        semester_year=2026,
        semester_number=2,
    )

    assert ok is True
    queue_messages = captured_publishes.messages_for(settings.notification_queue_name)
    assert len(queue_messages) == 1

    event = queue_messages[0]
    assert event["message_type"] == "lecturer_constraint_edited_by_secretary"
    assert event["recipient_user_ids"] == [7]
    assert event["metadata"]["constraint_id"] == 99
    assert "secretary" in event["payload"]["body"].lower()


async def test_publish_schedule_published_fans_out_to_all_semester_lecturers(
    captured_publishes,
    patch_async,
) -> None:
    patch_async(
        lecturer_courses_repo,
        "list_unique_lecturer_ids_for_semester",
        [11, 22, 33],
    )

    ok = await lecturer_events.publish_schedule_published(
        schedule_id=15,
        semester_year=2027,
        semester_number=1,
    )

    assert ok is True
    queue_messages = captured_publishes.messages_for(settings.notification_queue_name)
    assert len(queue_messages) == 1
    event = queue_messages[0]
    assert event["message_type"] == "schedule_published"
    assert event["recipient_user_ids"] == [11, 22, 33]
    assert event["metadata"]["schedule_id"] == 15
    assert any(u.endswith("/schedules/15") for u in event["payload"]["urls"])


async def test_publish_schedule_published_skips_when_no_recipients(
    captured_publishes,
    patch_async,
) -> None:
    patch_async(
        lecturer_courses_repo,
        "list_unique_lecturer_ids_for_semester",
        [],
    )

    ok = await lecturer_events.publish_schedule_published(
        schedule_id=15,
        semester_year=2027,
        semester_number=1,
    )

    assert ok is False
    assert captured_publishes.messages_for(settings.notification_queue_name) == []


async def test_publishers_swallow_rabbitmq_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the broker is unreachable, the helper must not raise."""

    async def _boom(_queue: str, _msg: dict) -> None:
        raise RuntimeError("broker unreachable")

    from src.rabbitmq.rabbitmq import rabbitmq

    monkeypatch.setattr(rabbitmq, "publish", _boom)

    ok = await lecturer_events.publish_constraint_saved_by_lecturer(
        constraint_id=1,
        lecturer_internal_id=1,
        semester_year=2027,
        semester_number=1,
    )
    assert ok is False
