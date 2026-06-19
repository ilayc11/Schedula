"""Tests for the change-period start per-lecturer schedule snapshot."""

from __future__ import annotations

from datetime import date, time

import pytest

from src.config import settings
from src.notifications import period_events
from src.repositories import lecturer_courses as lecturer_courses_repo
from src.repositories import period_notification_events as period_events_repo
from src.repositories import schedule_queries as schedule_queries_repo
from src.repositories import schedules as schedules_repo


@pytest.fixture
def in_memory_event_table(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
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


async def test_change_start_snapshot_fans_out_per_lecturer_with_session_summary(
    captured_publishes,
    patch_async,
    patch_async_factory,
    in_memory_event_table,
) -> None:
    patch_async(schedules_repo, "get_latest_schedule_for_semester", {"schedule_id": 15})
    patch_async(lecturer_courses_repo, "list_unique_lecturer_ids_for_semester", [101, 202])

    sessions_by_lecturer = {
        101: [
            {
                "course_name": "Algorithms",
                "day_of_week": 2,
                "start_time": time(10, 0),
                "end_time": time(12, 0),
                "group_number": 1,
            }
        ],
        202: [
            {
                "course_name": "Operating Systems",
                "day_of_week": 4,
                "start_time": time(14, 0),
                "end_time": time(16, 0),
                "group_number": 2,
            },
            {
                "course_name": "Databases",
                "day_of_week": 6,
                "start_time": time(9, 0),
                "end_time": time(11, 0),
                "group_number": 1,
            },
        ],
    }

    async def fake_get_detailed_schedule(*, schedule_id: int, lecturer_internal_id: int) -> list[dict]:
        assert schedule_id == 15
        return sessions_by_lecturer.get(lecturer_internal_id, [])

    patch_async_factory(schedule_queries_repo, "get_detailed_schedule", fake_get_detailed_schedule)

    await period_events._process_change_start_schedule_snapshots(
        semester_year=2027,
        semester_number=1,
        event_date=date(2027, 9, 15),
        source="test",
    )

    queue_messages = captured_publishes.messages_for(settings.notification_queue_name)
    assert len(queue_messages) == 2

    by_recipient = {evt["recipient_user_ids"][0]: evt for evt in queue_messages}
    assert set(by_recipient) == {101, 202}

    for evt in queue_messages:
        assert evt["message_type"] == "change_start_schedule_snapshot"
        assert evt["metadata"]["schedule_id"] == 15
        assert evt["payload"]["urls"]
        assert evt["payload"]["urls"][0].endswith("/schedules/15")

    body_101 = by_recipient[101]["payload"]["body"]
    assert "Algorithms" in body_101
    assert "Monday" in body_101  # day_of_week 2 => Monday
    assert "10:00-12:00" in body_101

    body_202 = by_recipient[202]["payload"]["body"]
    assert "Operating Systems" in body_202
    assert "Databases" in body_202


async def test_change_start_snapshot_is_idempotent(
    captured_publishes,
    patch_async,
    patch_async_factory,
    in_memory_event_table,
) -> None:
    patch_async(schedules_repo, "get_latest_schedule_for_semester", {"schedule_id": 15})
    patch_async(lecturer_courses_repo, "list_unique_lecturer_ids_for_semester", [101])

    async def fake_get_detailed_schedule(**_kwargs) -> list[dict]:
        return []

    patch_async_factory(schedule_queries_repo, "get_detailed_schedule", fake_get_detailed_schedule)

    await period_events._process_change_start_schedule_snapshots(
        semester_year=2027, semester_number=1, event_date=date(2027, 9, 15), source="test",
    )
    await period_events._process_change_start_schedule_snapshots(
        semester_year=2027, semester_number=1, event_date=date(2027, 9, 15), source="test",
    )

    assert len(captured_publishes.messages_for(settings.notification_queue_name)) == 1


async def test_change_start_snapshot_skips_when_no_schedule_exists(
    captured_publishes,
    patch_async,
    in_memory_event_table,
) -> None:
    patch_async(schedules_repo, "get_latest_schedule_for_semester", None)

    await period_events._process_change_start_schedule_snapshots(
        semester_year=2027, semester_number=1, event_date=date(2027, 9, 15), source="test",
    )

    assert captured_publishes.messages_for(settings.notification_queue_name) == []
    # The idempotency row must NOT have been reserved, so a later run with a
    # schedule in place can still fan out.
    assert in_memory_event_table == []


async def test_change_start_in_process_semester_time_events_triggers_snapshot(
    captured_publishes,
    patch_async,
    patch_async_factory,
    in_memory_event_table,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    semester = {
        "semester_year": 2027,
        "semester_number": 1,
        "constraint_start_date": date(2027, 8, 1),
        "constraint_end_date": date(2027, 9, 1),
        "change_period_start": date(2027, 9, 15),
        "change_period_end": date(2027, 9, 30),
        "status": "CHA",
    }
    monkeypatch.setattr(period_events, "_now_utc_date", lambda: semester["change_period_start"])

    patch_async(lecturer_courses_repo, "list_unique_lecturer_ids_for_semester", [101])
    patch_async(schedules_repo, "get_latest_schedule_for_semester", {"schedule_id": 7})

    async def fake_get_detailed_schedule(**_kwargs) -> list[dict]:
        return []

    patch_async_factory(schedule_queries_repo, "get_detailed_schedule", fake_get_detailed_schedule)

    await period_events.process_semester_time_events(semester, source="test")

    queue_messages = captured_publishes.messages_for(settings.notification_queue_name)
    # First message is the broadcast period_transition (event_key=change_start),
    # second is the per-lecturer change_start_schedule_snapshot.
    message_types = [evt["message_type"] for evt in queue_messages]
    assert "period_transition" in message_types
    assert "change_start_schedule_snapshot" in message_types
