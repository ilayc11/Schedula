"""Shared fixtures for notification tests.

These tests exercise the notification helpers in isolation by patching the
RabbitMQ publish call and any repository functions reached from the helpers.
They do not require a real database, RabbitMQ broker, or HTTP server.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable

import pytest

from src.rabbitmq.rabbitmq import rabbitmq


class _CapturingPublisher:
    """Stand-in for ``rabbitmq.publish`` that records every call."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def __call__(self, queue_name: str, message: dict) -> None:
        # Store a shallow copy so callers can keep mutating the dict.
        self.calls.append((queue_name, dict(message)))

    def messages_for(self, queue_name: str) -> list[dict]:
        return [event for q, event in self.calls if q == queue_name]


@pytest.fixture
def captured_publishes(monkeypatch: pytest.MonkeyPatch) -> _CapturingPublisher:
    """Replace ``rabbitmq.publish`` with an in-memory recorder."""
    publisher = _CapturingPublisher()
    monkeypatch.setattr(rabbitmq, "publish", publisher)
    return publisher


@pytest.fixture
def patch_async(monkeypatch: pytest.MonkeyPatch) -> Callable[[object, str, Any], None]:
    """Helper to monkeypatch a function with an async stub returning a fixed value."""

    def _patch(target: object, name: str, return_value: Any) -> None:
        async def _stub(*_args: Any, **_kwargs: Any) -> Any:
            return return_value

        monkeypatch.setattr(target, name, _stub)

    return _patch


@pytest.fixture
def patch_async_factory(monkeypatch: pytest.MonkeyPatch) -> Callable[[object, str, Callable[..., Awaitable[Any]]], None]:
    """Helper to monkeypatch a function with a custom async callable."""

    def _patch(target: object, name: str, coro_factory: Callable[..., Awaitable[Any]]) -> None:
        monkeypatch.setattr(target, name, coro_factory)

    return _patch
