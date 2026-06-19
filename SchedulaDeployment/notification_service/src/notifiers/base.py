from abc import ABC, abstractmethod
from typing import Any, Mapping


class AbstractNotifier(ABC):
    """Base abstraction for all notification channel providers."""

    channel: str

    @abstractmethod
    def can_send(self, profile: Mapping[str, Any]) -> bool:
        """Return whether this notifier can send using the provided delivery profile."""

    @abstractmethod
    async def send(self, profile: Mapping[str, Any], title: str, body: str) -> bool:
        """Send a notification. Returns True on success."""
