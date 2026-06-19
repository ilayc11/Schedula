"""Tests for the 48h-before-start period warnings."""

from __future__ import annotations

from datetime import date

import pytest

from src.config import settings
from src.notifications import period_events
from src.repositories import lecturer_courses as lecturer_courses_repo
from src.repositories import period_notification_events as period_events_repo


def _semester_row() -> dict:
    return {
        "semester_year": 2027,
        "semester_number": 1,
        "semester_start_date": date(2027, 10, 1),
        "semester_end_date": date(2028, 2, 1),
        "constraint_start_date": date(2027, 8, 1),
        "constraint_end_date": date(2027, 9, 1),
        "change_period_start": date(2027, 9, 15),
        "change_period_end": date(2027, 9, 30),
        "status": "SET",
    }


@pytest.fixture
def in_memory_event_table(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Replace the period_notification_events repo with an in-memory store."""
    storage: list[dict] = []
    next_id = {"value": 0}

    async def fake_reserve_event(
        *,
        semester_year: int,
        semester_number: int,
        event_key: str,
        event_date: date,
        payload: dict,
        source: str,
    ) -> dict | None:
        for row in storage:
            if (
                row["semester_year"] == semester_year
                and row["semester_number"] == semester_number
                and row["event_key"] == event_key
                and row["event_date"] == event_date
            ):
                return dict(row)

        next_id["value"] += 1
        row = {
            "event_id": next_id["value"],
            "semester_year": semester_year,
            "semester_number": semester_number,
            "event_key": event_key,
            "event_date": event_date,
            "payload": payload,
            "source": source,
            "published_at": None,
        }
        storage.append(row)
        return dict(row)

    async def fake_mark_published(event_id: int) -> dict | None:
        for row in storage:
            if row["event_id"] == event_id:
                row["published_at"] = "marked"
                return dict(row)
        return None

    monkeypatch.setattr(period_events_repo, "reserve_event", fake_reserve_event)
    monkeypatch.setattr(period_events_repo, "mark_published", fake_mark_published)
    return storage


async def test_constraint_starting_48h_fires_on_pre_start_day(
    captured_publishes,
    patch_async,
    in_memory_event_table,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    semester = _semester_row()
    monkeypatch.setattr(
        period_events,
        "_now_utc_date",
        lambda: semester["constraint_start_date"] - period_events.timedelta(days=2),
    )
    patch_async(lecturer_courses_repo, "list_unique_lecturer_ids_for_semester", [101])

    await period_events.process_semester_time_events(semester, source="test")

    queue_messages = captured_publishes.messages_for(settings.notification_queue_name)
    assert len(queue_messages) == 1
    event = queue_messages[0]
    assert event["message_type"] == "period_transition"
    assert event["metadata"]["period_type"] == "constraint"
    assert event["metadata"]["transition_type"] == "starting_soon"
    assert event["metadata"]["warning_hours"] == 48
    assert "starting soon" in event["payload"]["title"].lower()


async def test_change_starting_48h_fires_on_pre_change_start_day(
    captured_publishes,
    patch_async,
    in_memory_event_table,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    semester = _semester_row()
    monkeypatch.setattr(
        period_events,
        "_now_utc_date",
        lambda: semester["change_period_start"] - period_events.timedelta(days=2),
    )
    patch_async(lecturer_courses_repo, "list_unique_lecturer_ids_for_semester", [101, 202])

    await period_events.process_semester_time_events(semester, source="test")

    queue_messages = captured_publishes.messages_for(settings.notification_queue_name)
    assert len(queue_messages) == 1
    event = queue_messages[0]
    assert event["metadata"]["period_type"] == "change"
    assert event["metadata"]["transition_type"] == "starting_soon"
    assert event["recipient_user_ids"] == [101, 202]


async def test_starting_soon_is_idempotent_across_two_runs(
    captured_publishes,
    patch_async,
    in_memory_event_table,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    semester = _semester_row()
    monkeypatch.setattr(
        period_events,
        "_now_utc_date",
        lambda: semester["constraint_start_date"] - period_events.timedelta(days=2),
    )
    patch_async(lecturer_courses_repo, "list_unique_lecturer_ids_for_semester", [101])

    await period_events.process_semester_time_events(semester, source="test")
    await period_events.process_semester_time_events(semester, source="test")

    queue_messages = captured_publishes.messages_for(settings.notification_queue_name)
    assert len(queue_messages) == 1, "Second invocation must be deduplicated"
