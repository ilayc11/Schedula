"""Tests for ``_send_notification_message`` dispatching new lecturer events."""

from __future__ import annotations

from typing import Any, Mapping

import pytest

from src import main
from src.notifiers.base import AbstractNotifier
from src.repositories import user_notifications as user_notifications_repo


class _FakeNotifier(AbstractNotifier):
    channel = "fake"

    def __init__(self) -> None:
        self.sent: list[tuple[Mapping[str, Any], str, str]] = []

    def can_send(self, profile: Mapping[str, Any]) -> bool:
        return True

    async def send(self, profile: Mapping[str, Any], title: str, body: str) -> bool:
        self.sent.append((dict(profile), title, body))
        return True


@pytest.fixture
def fake_notifier(monkeypatch: pytest.MonkeyPatch) -> _FakeNotifier:
    fake = _FakeNotifier()
    monkeypatch.setattr(main, "recipient_notifiers", [fake])
    return fake


@pytest.fixture
def fake_profiles(monkeypatch: pytest.MonkeyPatch) -> dict[int, dict[str, Any]]:
    profiles: dict[int, dict[str, Any]] = {}

    async def fake_get_delivery_profiles(user_ids):
        return {uid: profiles[uid] for uid in user_ids if uid in profiles}

    monkeypatch.setattr(
        user_notifications_repo,
        "get_delivery_profiles_for_users",
        fake_get_delivery_profiles,
    )
    return profiles


async def test_dispatch_lecturer_constraint_saved(fake_notifier, fake_profiles) -> None:
    fake_profiles[42] = {"user_internal_id": 42, "email": "l@example.com", "email_enabled": True}

    await main._send_notification_message(
        {
            "schema_version": "2.0",
            "message_type": "lecturer_constraint_saved",
            "recipient_user_ids": [42],
            "metadata": {"event_type": "lecturer_constraint_saved"},
            "payload": {
                "title": "Constraint saved",
                "body": "Your constraint for semester 2027/1 has been saved successfully.",
                "urls": [],
            },
        }
    )

    assert len(fake_notifier.sent) == 1
    _, title, body = fake_notifier.sent[0]
    assert title == "Constraint saved"
    assert "2027/1" in body


async def test_dispatch_schedule_published_fans_out_to_all_recipients(
    fake_notifier, fake_profiles
) -> None:
    for uid in (11, 22, 33):
        fake_profiles[uid] = {"user_internal_id": uid, "email": f"l{uid}@x.com", "email_enabled": True}

    await main._send_notification_message(
        {
            "schema_version": "2.0",
            "message_type": "schedule_published",
            "recipient_user_ids": [11, 22, 33],
            "metadata": {"event_type": "schedule_published", "schedule_id": 15},
            "payload": {
                "title": "Schedule published",
                "body": "The schedule for semester 2027/1 has been officially published.",
                "urls": [],
            },
        }
    )

    assert len(fake_notifier.sent) == 3
    delivered_user_ids = {p["user_internal_id"] for p, _t, _b in fake_notifier.sent}
    assert delivered_user_ids == {11, 22, 33}


async def test_dispatch_change_start_schedule_snapshot(fake_notifier, fake_profiles) -> None:
    fake_profiles[101] = {"user_internal_id": 101, "email": "l@example.com", "email_enabled": True}

    body_text = (
        "The schedule changes period for semester 2027/1 has started. "
        "Your current sessions:\n- Algorithms: Monday 10:00-12:00"
    )
    await main._send_notification_message(
        {
            "schema_version": "2.0",
            "message_type": "change_start_schedule_snapshot",
            "recipient_user_ids": [101],
            "metadata": {
                "event_type": "change_start_schedule_snapshot",
                "schedule_id": 15,
                "semester_year": 2027,
                "semester_number": 1,
            },
            "payload": {
                "title": "Your schedule for 2027/1",
                "body": body_text,
                "urls": ["https://schedula.local/schedules/15"],
            },
        }
    )

    # Body has URLs, so the dispatcher uses the URL path and skips per-recipient
    # delivery via notifiers. That matches the existing behavior of period
    # notifications when explicit URLs are present.
    assert fake_notifier.sent == []


async def test_dispatch_starting_soon_period_transition(fake_notifier, fake_profiles) -> None:
    fake_profiles[42] = {"user_internal_id": 42, "email": "l@example.com", "email_enabled": True}

    await main._send_notification_message(
        {
            "schema_version": "2.0",
            "message_type": "period_transition",
            "recipient_user_ids": [42],
            "metadata": {
                "event_type": "period_transition",
                "period_type": "constraint",
                "transition_type": "starting_soon",
                "warning_hours": 48,
                "semester_year": 2027,
                "semester_number": 1,
            },
            "payload": {
                "title": "Constraint submission period starting soon",
                "body": "Constraint submission period for semester 2027/1 starts in about 48 hours.",
                "urls": [],
            },
        }
    )

    assert len(fake_notifier.sent) == 1
    _, title, body = fake_notifier.sent[0]
    assert "starting soon" in title.lower()
    assert "48 hours" in body
