"""Tests for the FALSE->TRUE is_published transition wiring."""

from __future__ import annotations

import importlib
from datetime import datetime, timezone

import pytest

from src.config import settings
from src.models.schedule import ScheduleUpdate
from src.repositories import lecturer_courses as lecturer_courses_repo
from src.repositories import schedules as schedules_repo


@pytest.fixture
def fake_schedule_state(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Replace schedules_repo.get_schedule + update_schedule with an in-memory schedule."""
    now = datetime.now(timezone.utc)
    state = {
        "schedule_id": 15,
        "semester_year": 2027,
        "semester_number": 1,
        "is_draft": True,
        "is_published": False,
        "published_at": None,
        "created_at": now,
        "last_update": now,
    }

    async def fake_get_schedule(schedule_id: int) -> dict | None:
        if schedule_id != state["schedule_id"]:
            return None
        return dict(state)

    async def fake_update_schedule(schedule_id: int, updates: dict) -> dict | None:
        if schedule_id != state["schedule_id"]:
            return None
        state.update(updates)
        return dict(state)

    monkeypatch.setattr(schedules_repo, "get_schedule", fake_get_schedule)
    monkeypatch.setattr(schedules_repo, "update_schedule", fake_update_schedule)
    return state


async def test_publishing_a_draft_emits_schedule_published(
    captured_publishes,
    patch_async,
    fake_schedule_state,
) -> None:
    patch_async(lecturer_courses_repo, "list_unique_lecturer_ids_for_semester", [101, 202])

    # Import the route after monkeypatching to ensure consistent module state.
    schedules_route = importlib.import_module("src.routes.external.secretary.schedules")

    payload = ScheduleUpdate(is_published=True, is_draft=False)
    result = await schedules_route.update_schedule_metadata(
        request=None,  # the route does not read the request for this path
        schedule_id=15,
        payload=payload,
    )

    assert bool(result.is_published) is True

    queue_messages = captured_publishes.messages_for(settings.notification_queue_name)
    assert len(queue_messages) == 1
    event = queue_messages[0]
    assert event["message_type"] == "schedule_published"
    assert event["recipient_user_ids"] == [101, 202]
    assert event["metadata"]["schedule_id"] == 15


async def test_republishing_already_published_schedule_does_not_renotify(
    captured_publishes,
    patch_async,
    fake_schedule_state,
) -> None:
    fake_schedule_state["is_published"] = True

    patch_async(lecturer_courses_repo, "list_unique_lecturer_ids_for_semester", [101])

    schedules_route = importlib.import_module("src.routes.external.secretary.schedules")

    payload = ScheduleUpdate(is_published=True)
    await schedules_route.update_schedule_metadata(
        request=None,
        schedule_id=15,
        payload=payload,
    )

    assert captured_publishes.messages_for(settings.notification_queue_name) == []
