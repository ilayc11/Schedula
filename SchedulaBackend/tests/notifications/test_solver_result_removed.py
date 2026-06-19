"""Regression test: solver responses must no longer publish to notifications_queue."""

from __future__ import annotations

import json
from typing import Any

import pytest

from src.config import settings
from src.rabbitmq import consumer as rabbit_consumer
from src.repositories import solver_runs as solver_runs_repo


class _FakeMessage:
    """Minimal stand-in for ``aio_pika.IncomingMessage`` used by the consumer."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.body = json.dumps(payload).encode()
        self.acked = False
        self.rejected: bool | None = None

    async def ack(self) -> None:
        self.acked = True

    async def reject(self, requeue: bool = False) -> None:
        self.rejected = requeue


async def test_solver_response_does_not_publish_notifications(
    captured_publishes,
    patch_async,
) -> None:
    patch_async(
        solver_runs_repo,
        "update_run_by_semester",
        {"run_id": 1, "schedule_id": 10, "status": "solved"},
    )

    payload = {
        "semester_year": 2027,
        "semester_number": 1,
        "status": "solved",
        "schedule_id": 10,
    }
    message = _FakeMessage(payload)

    await rabbit_consumer._process_solver_response(message)

    assert message.acked is True
    assert captured_publishes.messages_for(settings.notification_queue_name) == [], (
        "Solver responses must no longer publish lecturer notifications"
    )


async def test_consumer_does_not_import_removed_repo() -> None:
    """The deleted ``solver_result_notification_events`` import must stay gone."""
    import importlib

    importlib.reload(rabbit_consumer)
    assert "solver_result_notification_events" not in rabbit_consumer.__dict__
