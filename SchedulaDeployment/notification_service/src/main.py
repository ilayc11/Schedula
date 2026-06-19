import asyncio
import json
import logging
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import apprise
from aio_pika import connect_robust
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from src.config import settings
from src.db import db
from src.models import (
    NormalizedNotification,
    NotificationMetadata,
    PeriodNotificationPreviewResponse,
    PeriodNotificationRequest,
    PeriodNotificationSendResponse,
    TelegramWebhookDeleteResponse,
    TelegramWebhookSetRequest,
    TelegramWebhookSetResponse,
    normalize_queue_message,
)
from src.notifiers import AbstractNotifier, EmailAppriseNotifier, TelegramNotifier
from src.period_messages import build_period_notification_content
from src.repositories import user_notifications as user_notifications_repo

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


default_apprise = apprise.Apprise()
if settings.apprise_urls:
    for url in settings.apprise_urls.split(","):
        if url.strip():
            default_apprise.add(url.strip())

telegram_notifier = TelegramNotifier()
email_notifier = EmailAppriseNotifier()
recipient_notifiers: list[AbstractNotifier] = [telegram_notifier, email_notifier]


async def _send_with_urls(urls: list[str], title: str, body: str) -> bool:
    if not urls:
        return False

    sender = apprise.Apprise()
    for url in urls:
        sender.add(url)

    try:
        await sender.async_notify(body=body, title=title)
        return True
    except Exception as exc:
        logger.error("Failed to send notification via Apprise URLs: %s", exc)
        return False


async def _send_to_recipients(notification: NormalizedNotification) -> dict[str, int]:
    recipient_user_ids = list(dict.fromkeys(notification.recipient_user_ids))
    profiles = await user_notifications_repo.get_delivery_profiles_for_users(recipient_user_ids)
    if not profiles:
        logger.warning("No recipient delivery profiles found for user IDs: %s", recipient_user_ids)
        return {"requested": len(recipient_user_ids), "attempted": 0, "delivered": 0}

    delivered = 0
    attempted = 0
    for user_id in recipient_user_ids:
        profile = profiles.get(user_id)
        if not profile:
            continue

        active_notifiers = [notifier for notifier in recipient_notifiers if notifier.can_send(profile)]
        if not active_notifiers:
            logger.info("No enabled delivery channels for user %s", user_id)
            continue

        attempted += 1
        sent = False
        for notifier in active_notifiers:
            if await notifier.send(profile, notification.title, notification.body):
                sent = True

        if sent:
            delivered += 1

    logger.info(
        "Recipient delivery summary: delivered=%d attempted=%d requested=%d",
        delivered,
        attempted,
        len(recipient_user_ids),
    )
    return {"requested": len(recipient_user_ids), "attempted": attempted, "delivered": delivered}


async def _send_notification_message(raw_data: dict) -> None:
    notification = normalize_queue_message(raw_data)
    if not notification.body:
        logger.warning("Received notification request with empty body")
        return

    if notification.urls:
        sent = await _send_with_urls(notification.urls, notification.title, notification.body)
        if sent:
            logger.info("Notification sent successfully: %s", notification.title)
        return

    if notification.recipient_user_ids:
        await _send_to_recipients(notification)
        return

    try:
        await default_apprise.async_notify(
            body=notification.body,
            title=notification.title,
        )
        logger.info("Notification sent successfully: %s", notification.title)
    except Exception as exc:
        logger.error("Failed to send notification: %s", exc)


async def _consume_queue_once() -> None:
    logger.info("Connecting to RabbitMQ at %s", settings.rabbitmq_url)
    connection = await connect_robust(settings.rabbitmq_url)

    try:
        channel = await connection.channel()
        queue = await channel.declare_queue(settings.notification_queue_name, durable=True)
        logger.info("Waiting for messages in %s", settings.notification_queue_name)

        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    try:
                        body = json.loads(message.body.decode())
                        await _send_notification_message(body)
                    except Exception as exc:
                        logger.error("Error processing notification message: %s", exc)
    finally:
        await connection.close()


async def _notification_consumer_loop() -> None:
    while True:
        try:
            await _consume_queue_once()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Notification consumer loop failed: %s", exc)
            await asyncio.sleep(5)


def _build_telegram_link(token: str) -> str:
    return f"https://t.me/{settings.telegram_bot_name}?start={token}"


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _get_token_expiration(notif_data: dict | None) -> datetime | None:
    if not notif_data or not notif_data.get("telegram_token"):
        return None

    base_time = _parse_datetime(notif_data.get("updated_at")) or _parse_datetime(notif_data.get("created_at"))
    if base_time is None:
        return None

    ttl_seconds = max(0, int(settings.telegram_link_token_ttl_seconds))
    return base_time + timedelta(seconds=ttl_seconds)


def _is_token_expired(notif_data: dict | None) -> bool:
    expires_at = _get_token_expiration(notif_data)
    if expires_at is None:
        return False
    return datetime.now(timezone.utc) > expires_at.astimezone(timezone.utc)


def _build_link_status(notif_data: dict | None) -> dict:
    is_linked = bool(notif_data and notif_data.get("telegram_chat_id"))
    token = notif_data.get("telegram_token") if notif_data else None
    token_expired = _is_token_expired(notif_data) if token else False
    has_active_token = bool(token and not token_expired)
    expires_at = _get_token_expiration(notif_data)

    return {
        "is_linked": is_linked,
        "link_in_progress": bool((not is_linked) and has_active_token),
        "telegram_link": _build_telegram_link(token) if has_active_token else None,
        "link_expires_at": expires_at.isoformat() if expires_at else None,
    }


async def _ensure_link_token(user_internal_id: int, regenerate: bool = False) -> dict:
    if not await user_notifications_repo.user_exists(user_internal_id):
        raise HTTPException(status_code=404, detail="User not found")

    notif_data = await user_notifications_repo.get_by_user_id(user_internal_id)
    should_generate = (
        notif_data is None
        or not notif_data.get("telegram_token")
        or _is_token_expired(notif_data)
        or regenerate
    )

    if should_generate:
        notif_data = await user_notifications_repo.set_link_token(
            user_internal_id,
            secrets.token_urlsafe(16),
        )

    if notif_data is None:
        raise HTTPException(status_code=500, detail="Failed to initialize Telegram linking state")

    return notif_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()

    consumer_task = asyncio.create_task(_notification_consumer_loop())
    await telegram_notifier.ensure_webhook_registration()

    try:
        yield
    finally:
        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass
        await db.disconnect()


app = FastAPI(
    title="Schedula Notification Service",
    lifespan=lifespan,
)


@app.get("/health", response_class=PlainTextResponse)
async def health() -> str:
    return "OK"


@app.post("/webhooks/telegram")
async def telegram_webhook(request: Request):
    received_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if not telegram_notifier.is_valid_webhook_secret(received_secret):
        return JSONResponse({"detail": "Invalid webhook secret"}, status_code=401)

    try:
        data = await request.json()
    except Exception:
        return {"status": "ok"}

    return await telegram_notifier.handle_update(data)


@app.post(
    "/internal/telegram-webhook/set",
    response_model=TelegramWebhookSetResponse,
)
async def internal_set_webhook(
    payload: TelegramWebhookSetRequest,
) -> TelegramWebhookSetResponse:
    try:
        return await telegram_notifier.set_webhook(payload.public_url, payload.secret_token)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post(
    "/internal/telegram-webhook/delete",
    response_model=TelegramWebhookDeleteResponse,
)
async def internal_delete_webhook(
    drop_pending_updates: bool = False,
) -> TelegramWebhookDeleteResponse:
    try:
        return await telegram_notifier.delete_webhook(drop_pending_updates=drop_pending_updates)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.get("/internal/telegram-link/status/{user_internal_id}")
async def internal_get_telegram_link_status(user_internal_id: int) -> dict:
    """Return Telegram linking status without mutating token state."""
    notif_data = await user_notifications_repo.get_by_user_id(user_internal_id)
    return _build_link_status(notif_data)


def _build_period_metadata(payload: PeriodNotificationRequest) -> NotificationMetadata:
    return NotificationMetadata(
        event_type="period_transition",
        semester_year=payload.semester_year,
        semester_number=payload.semester_number,
        period_type=payload.period_type,
        transition_type=payload.transition_type,
        warning_hours=payload.warning_hours,
        transition_date=payload.transition_date,
        old_status=payload.old_status,
        new_status=payload.new_status,
        status=payload.new_status,
    )


@app.post(
    "/internal/period-notifications/preview",
    response_model=PeriodNotificationPreviewResponse,
)
async def preview_period_notification(payload: PeriodNotificationRequest) -> PeriodNotificationPreviewResponse:
    """Build and return the notification text for a period event without sending."""
    title, body = build_period_notification_content(payload)
    return PeriodNotificationPreviewResponse(
        title=title,
        body=body,
        metadata=_build_period_metadata(payload),
    )


@app.post(
    "/internal/period-notifications/send",
    response_model=PeriodNotificationSendResponse,
)
async def send_period_notification(payload: PeriodNotificationRequest) -> PeriodNotificationSendResponse:
    """Send a period event notification to explicit recipients using configured channels."""
    if not payload.recipient_user_ids:
        raise HTTPException(status_code=400, detail="recipient_user_ids must contain at least one user ID")

    title, body = build_period_notification_content(payload)
    summary = await _send_to_recipients(
        NormalizedNotification(
            title=title,
            body=body,
            urls=[],
            recipient_user_ids=payload.recipient_user_ids,
            metadata=_build_period_metadata(payload),
        )
    )

    return PeriodNotificationSendResponse(
        requested=summary["requested"],
        attempted=summary["attempted"],
        delivered=summary["delivered"],
        title=title,
    )


@app.post("/internal/telegram-link/start/{user_internal_id}")
async def internal_start_telegram_link(user_internal_id: int) -> dict:
    """Create or reuse Telegram deep-link token and return current linking state."""
    notif_data = await _ensure_link_token(user_internal_id=user_internal_id, regenerate=False)
    return _build_link_status(notif_data)


@app.get("/internal/telegram-link/{user_internal_id}")
async def internal_get_telegram_link(user_internal_id: int) -> dict:
    """Backward-compatible endpoint that ensures token exists before returning state."""
    notif_data = await _ensure_link_token(user_internal_id=user_internal_id, regenerate=False)
    return _build_link_status(notif_data)
