"""DEV ONLY - Telegram webhook runtime management routes"""
import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict

from src.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


class TelegramWebhookSetRequest(BaseModel):
    public_url: str = Field(..., min_length=1)
    secret_token: str | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "public_url": "https://abcd1234.trycloudflare.com",
                "secret_token": "my-secret-token"
            }
        }
    )


class TelegramWebhookResponse(BaseModel):
    telegram_ok: bool
    description: str | None = None
    previous_webhook_url: str | None = None
    webhook_url: str | None = None
    pending_update_count: int | None = None
    last_error_message: str | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "telegram_ok": True,
                "description": "Webhook was set",
                "previous_webhook_url": "https://old-url.trycloudflare.com/webhooks/telegram",
                "webhook_url": "https://abcd1234.trycloudflare.com/webhooks/telegram",
                "pending_update_count": 0,
                "last_error_message": None
            }
        }
    )


def _notification_base_url() -> str:
    base_url = settings.notification_service_base_url
    if not base_url:
        raise HTTPException(status_code=503, detail="Notification service base URL is not configured")
    return base_url.rstrip("/")


def _extract_error_detail(response: httpx.Response, fallback: str) -> str:
    try:
        return str(response.json().get("detail", fallback))
    except Exception:
        return fallback


async def _delegate_webhook_request(
    route_path: str,
    *,
    json_payload: dict[str, Any] | None = None,
    query_params: dict[str, Any] | None = None,
    error_message: str,
) -> dict[str, Any]:
    target_url = f"{_notification_base_url()}{route_path}"

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            response = await client.post(
                target_url,
                json=json_payload,
                params=query_params,
            )
    except Exception as exc:
        logger.error("Failed calling notification_service endpoint %s: %s", route_path, exc)
        raise HTTPException(status_code=502, detail="Failed contacting notification service")

    if response.status_code != 200:
        detail = _extract_error_detail(response, error_message)
        raise HTTPException(status_code=response.status_code, detail=detail)

    return response.json()


@router.post("/set", response_model=TelegramWebhookResponse)
async def set_telegram_webhook(payload: TelegramWebhookSetRequest) -> TelegramWebhookResponse:
    """Set Telegram webhook at runtime by delegating to notification_service."""
    response_data = await _delegate_webhook_request(
        "/internal/telegram-webhook/set",
        json_payload=payload.model_dump(exclude_none=True),
        error_message="Notification service failed to set webhook",
    )
    return TelegramWebhookResponse.model_validate(response_data)


@router.post("/delete", response_model=TelegramWebhookResponse)
async def delete_telegram_webhook(
    drop_pending_updates: bool = Query(False, description="Drop pending updates in Telegram"),
) -> TelegramWebhookResponse:
    """Delete Telegram webhook at runtime by delegating to notification_service."""
    response_data = await _delegate_webhook_request(
        "/internal/telegram-webhook/delete",
        query_params={"drop_pending_updates": drop_pending_updates},
        error_message="Notification service failed to delete webhook",
    )
    return TelegramWebhookResponse.model_validate(response_data)
