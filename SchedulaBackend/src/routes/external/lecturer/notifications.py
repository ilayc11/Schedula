import logging
from typing import Any, Dict

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from src.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


class TelegramLinkStatusResponse(BaseModel):
    is_linked: bool
    link_in_progress: bool
    telegram_link: str | None = None
    link_expires_at: str | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "is_linked": False,
                "link_in_progress": True,
                "telegram_link": "https://t.me/Schedula_BotBot?start=abc123token",
                "link_expires_at": "2026-01-12T10:30:00Z"
            }
        }
    )


def _get_user_internal_id(request: Request) -> int:
    user_internal_id = getattr(request.state, "user_internal_id", None)
    if user_internal_id is None:
        raise HTTPException(status_code=401, detail="User not authenticated")
    return int(user_internal_id)


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


async def _delegate_link_request(route_path: str, error_message: str) -> Dict[str, Any]:
    target_url = f"{_notification_base_url()}{route_path}"

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            response = await client.get(target_url)
    except Exception as exc:
        logger.error("Failed calling notification_service endpoint %s: %s", route_path, exc)
        raise HTTPException(status_code=502, detail="Failed contacting notification service")

    if response.status_code != 200:
        detail = _extract_error_detail(response, error_message)
        raise HTTPException(status_code=response.status_code, detail=detail)

    return response.json()


@router.get("/telegram-link/status", response_model=TelegramLinkStatusResponse)
async def get_telegram_link_status(request: Request):
    """Return Telegram linking state by delegating to notification_service."""
    user_internal_id = _get_user_internal_id(request)
    return await _delegate_link_request(
        f"/internal/telegram-link/status/{user_internal_id}",
        "Notification service failed to get Telegram link status",
    )


@router.post("/telegram-link/start", response_model=TelegramLinkStatusResponse)
async def start_telegram_link(request: Request):
    """Start Telegram linking flow by delegating to notification_service."""
    user_internal_id = _get_user_internal_id(request)
    target_url = f"{_notification_base_url()}/internal/telegram-link/start/{user_internal_id}"

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            response = await client.post(target_url)
    except Exception as exc:
        logger.error("Failed calling notification_service endpoint /internal/telegram-link/start/%s: %s", user_internal_id, exc)
        raise HTTPException(status_code=502, detail="Failed contacting notification service")

    if response.status_code != 200:
        detail = _extract_error_detail(response, "Notification service failed to start Telegram link flow")
        raise HTTPException(status_code=response.status_code, detail=detail)

    return response.json()


@router.get("/telegram-link", response_model=TelegramLinkStatusResponse)
async def get_telegram_link(request: Request):
    """
    Backward-compatible endpoint used by existing clients.

    Delegates to notification_service and returns current link state.
    """
    user_internal_id = _get_user_internal_id(request)
    return await _delegate_link_request(
        f"/internal/telegram-link/{user_internal_id}",
        "Notification service failed to get Telegram link",
    )
