from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class NotificationPayload(BaseModel):
    title: Optional[str] = None
    body: str
    urls: list[str] = Field(default_factory=list)


class NotificationMetadata(BaseModel):
    event_type: str = "generic"
    semester_year: Optional[int] = None
    semester_number: Optional[int] = None
    status: Optional[str] = None
    schedule_id: Optional[int] = None
    broken_constraints_count: Optional[int] = None
    period_type: Optional[Literal["constraint", "change", "status"]] = None
    transition_type: Optional[Literal["start", "starting_soon", "ending_soon", "ended", "changed"]] = None
    warning_hours: Optional[int] = None
    transition_date: Optional[str] = None
    old_status: Optional[str] = None
    new_status: Optional[str] = None


class TypedNotificationMessage(BaseModel):
    schema_version: str = "2.0"
    message_type: str = "generic"
    message_id: Optional[str] = None
    correlation_id: Optional[str] = None
    recipient_user_ids: list[int] = Field(default_factory=list)
    metadata: Optional[NotificationMetadata] = None
    payload: NotificationPayload


class LegacyNotificationMessage(BaseModel):
    title: Optional[str] = None
    body: str
    urls: list[str] = Field(default_factory=list)


class NormalizedNotification(BaseModel):
    title: str
    body: str
    urls: list[str] = Field(default_factory=list)
    recipient_user_ids: list[int] = Field(default_factory=list)
    metadata: Optional[NotificationMetadata] = None


class TelegramWebhookSetRequest(BaseModel):
    public_url: str
    secret_token: Optional[str] = None


class TelegramWebhookSetResponse(BaseModel):
    telegram_ok: bool
    description: Optional[str] = None
    webhook_url: Optional[str] = None
    pending_update_count: Optional[int] = None
    last_error_message: Optional[str] = None


class TelegramWebhookDeleteResponse(BaseModel):
    telegram_ok: bool
    description: Optional[str] = None
    previous_webhook_url: Optional[str] = None
    webhook_url: Optional[str] = None
    pending_update_count: Optional[int] = None
    last_error_message: Optional[str] = None


class PeriodNotificationRequest(BaseModel):
    semester_year: int
    semester_number: int
    period_type: Literal["constraint", "change", "status"]
    transition_type: Literal["start", "starting_soon", "ending_soon", "ended", "changed"]
    warning_hours: Optional[int] = None
    transition_date: Optional[str] = None
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    recipient_user_ids: list[int] = Field(default_factory=list)


class PeriodNotificationPreviewResponse(BaseModel):
    title: str
    body: str
    metadata: NotificationMetadata


class PeriodNotificationSendResponse(BaseModel):
    requested: int
    attempted: int
    delivered: int
    title: str


def normalize_queue_message(raw: dict[str, Any]) -> NormalizedNotification:
    """Support typed envelope and legacy message formats during migration."""
    if "payload" in raw and isinstance(raw.get("payload"), dict):
        typed = TypedNotificationMessage.model_validate(raw)
        return NormalizedNotification(
            title=typed.payload.title or "Schedula Notification",
            body=typed.payload.body,
            urls=typed.payload.urls,
            recipient_user_ids=typed.recipient_user_ids,
            metadata=typed.metadata,
        )

    legacy = LegacyNotificationMessage.model_validate(raw)
    return NormalizedNotification(
        title=legacy.title or "Schedula Notification",
        body=legacy.body,
        urls=legacy.urls,
        recipient_user_ids=[],
        metadata=None,
    )
