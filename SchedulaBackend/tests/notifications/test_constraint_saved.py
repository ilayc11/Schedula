"""Wiring test: the lecturer save route publishes lecturer_constraint_saved."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.config import settings
from src.models.constraint import ConstraintSavePayload
from src.repositories import constraints as constraints_repo
from src.routes.external.lecturer import constraints as lecturer_constraints_route


async def test_save_confirmed_constraint_publishes_lecturer_constraint_saved(
    captured_publishes,
    patch_async,
    patch_async_factory,
) -> None:
    patch_async(constraints_repo, "list_constraints_by_user", [])

    async def fake_create_constraint(_payload: dict) -> dict:
        return {"constraints_id": 88, "lecturer_internal_id": 42}

    patch_async_factory(constraints_repo, "create_constraint", fake_create_constraint)

    request = SimpleNamespace(state=SimpleNamespace(user_internal_id=42))
    payload = ConstraintSavePayload(
        semester_year=2027,
        semester_number=1,
        raw_text="No classes on Friday",
        structured_rules={
            "atomic_constraints": [
                {
                    "type": "block",
                    "days": [6],
                    "time_slot": {"start_hour": 8, "end_hour": 14},
                    "priority": "hard",
                }
            ]
        },
    )

    result = await lecturer_constraints_route.save_confirmed_constraint(
        request=request, payload=payload
    )

    assert result["status"] == "success"

    queue_messages = captured_publishes.messages_for(settings.notification_queue_name)
    assert len(queue_messages) == 1
    event = queue_messages[0]
    assert event["message_type"] == "lecturer_constraint_saved"
    assert event["recipient_user_ids"] == [42]
    assert event["metadata"]["constraint_id"] == 88
    assert event["metadata"]["semester_year"] == 2027
    assert event["metadata"]["semester_number"] == 1
