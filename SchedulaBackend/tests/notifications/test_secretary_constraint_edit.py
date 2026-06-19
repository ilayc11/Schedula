"""Wiring test: secretary constraint edits publish lecturer_constraint_edited_by_secretary."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.config import settings
from src.repositories import constraints as constraints_repo
from src.routes.external.secretary import manage_constraints as secretary_route


async def test_priority_update_publishes_secretary_edit_notification(
    captured_publishes,
    patch_async_factory,
) -> None:
    async def fake_update_constraint(constraints_id: int, updates: dict) -> dict:
        return {
            "constraints_id": constraints_id,
            "lecturer_internal_id": 42,
            "semester_year": 2027,
            "semester_number": 1,
            **updates,
        }

    patch_async_factory(constraints_repo, "update_constraint", fake_update_constraint)

    request = SimpleNamespace(state=SimpleNamespace(user_role="S", user_internal_id=999))
    payload = secretary_route.ConstraintPriorityUpdateRequest(secretary_override_as_hard=True)

    result = await secretary_route.update_constraint_priority(
        request=request, constraints_id=88, payload=payload
    )

    assert result["status"] == "success"

    queue_messages = captured_publishes.messages_for(settings.notification_queue_name)
    assert len(queue_messages) == 1
    event = queue_messages[0]
    assert event["message_type"] == "lecturer_constraint_edited_by_secretary"
    assert event["recipient_user_ids"] == [42]
    assert event["metadata"]["constraint_id"] == 88


async def test_priority_update_does_not_notify_when_constraint_missing(
    captured_publishes,
    patch_async,
) -> None:
    patch_async(constraints_repo, "update_constraint", None)

    request = SimpleNamespace(state=SimpleNamespace(user_role="S", user_internal_id=999))
    payload = secretary_route.ConstraintPriorityUpdateRequest(secretary_override_as_hard=False)

    with pytest.raises(Exception):
        await secretary_route.update_constraint_priority(
            request=request, constraints_id=88, payload=payload
        )

    assert captured_publishes.messages_for(settings.notification_queue_name) == []
