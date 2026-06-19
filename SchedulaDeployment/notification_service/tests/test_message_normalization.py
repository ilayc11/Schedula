"""Tests for ``normalize_queue_message`` with the new lecturer message_types."""

from __future__ import annotations

import pytest

from src.models import normalize_queue_message


def _envelope(message_type: str, *, body: str = "Hello.", urls: list[str] | None = None, recipients: list[int] | None = None) -> dict:
    return {
        "schema_version": "2.0",
        "message_type": message_type,
        "message_id": "msg-1",
        "recipient_user_ids": recipients or [42],
        "metadata": {"event_type": message_type},
        "payload": {
            "title": f"Title for {message_type}",
            "body": body,
            "urls": urls or [],
        },
    }


def test_normalize_lecturer_constraint_saved() -> None:
    result = normalize_queue_message(_envelope("lecturer_constraint_saved"))
    assert result.title == "Title for lecturer_constraint_saved"
    assert result.body == "Hello."
    assert result.recipient_user_ids == [42]


def test_normalize_lecturer_constraint_edited_by_secretary() -> None:
    result = normalize_queue_message(_envelope("lecturer_constraint_edited_by_secretary"))
    assert result.title == "Title for lecturer_constraint_edited_by_secretary"


def test_normalize_schedule_published_preserves_urls() -> None:
    raw = _envelope("schedule_published", urls=["https://schedula.local/schedules/15"], recipients=[1, 2, 3])
    result = normalize_queue_message(raw)
    assert result.recipient_user_ids == [1, 2, 3]
    assert result.urls == ["https://schedula.local/schedules/15"]


def test_normalize_change_start_schedule_snapshot() -> None:
    body = (
        "The schedule changes period for semester 2027/1 has started. "
        "Your current sessions:\n- Algorithms: Monday 10:00-12:00"
    )
    raw = _envelope(
        "change_start_schedule_snapshot",
        body=body,
        urls=["https://schedula.local/schedules/15"],
    )
    result = normalize_queue_message(raw)
    assert "Algorithms" in result.body
    assert "Monday 10:00-12:00" in result.body
    assert result.urls[0].endswith("/schedules/15")


def test_normalize_period_transition_with_starting_soon_transition_type() -> None:
    raw = {
        "schema_version": "2.0",
        "message_type": "period_transition",
        "message_id": "msg-2",
        "recipient_user_ids": [42],
        "metadata": {
            "event_type": "period_transition",
            "semester_year": 2027,
            "semester_number": 1,
            "period_type": "change",
            "transition_type": "starting_soon",
            "warning_hours": 48,
        },
        "payload": {
            "title": "Schedule changes period starting soon",
            "body": "Schedule changes period for semester 2027/1 starts in about 48 hours.",
            "urls": [],
        },
    }
    result = normalize_queue_message(raw)
    assert result.metadata is not None
    assert result.metadata.transition_type == "starting_soon"
    assert result.metadata.warning_hours == 48


def test_normalize_falls_back_to_default_title_when_missing() -> None:
    raw = _envelope("lecturer_constraint_saved")
    raw["payload"]["title"] = None
    result = normalize_queue_message(raw)
    assert result.title == "Schedula Notification"
