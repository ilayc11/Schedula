import logging
import time

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.config import settings

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])
logger = logging.getLogger(__name__)

_BODY_PARSE_ERROR_LOG_INTERVAL_SECONDS = 60.0
_last_body_parse_error_log_monotonic = 0.0


def _should_log_body_parse_error() -> bool:
    global _last_body_parse_error_log_monotonic

    now = time.monotonic()
    if now - _last_body_parse_error_log_monotonic >= _BODY_PARSE_ERROR_LOG_INTERVAL_SECONDS:
        _last_body_parse_error_log_monotonic = now
        return True

    return False


def _build_forward_headers(request: Request) -> dict[str, str]:
    headers: dict[str, str] = {}

    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret:
        headers["X-Telegram-Bot-Api-Secret-Token"] = secret

    content_type = request.headers.get("Content-Type")
    if content_type:
        headers["Content-Type"] = content_type

    return headers


@router.post(
    "/telegram",
    responses={
        200: {
            "description": "Webhook forwarded successfully",
            "content": {
                "application/json": {
                    "example": {
                        "status": "ok"
                    }
                }
            },
        },
        502: {
            "description": "Forwarding failed or upstream response was invalid",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Failed forwarding Telegram webhook"
                    }
                }
            },
        },
        503: {
            "description": "Notification service URL is not configured",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Notification service base URL is not configured"
                    }
                }
            },
        },
    },
)
async def telegram_webhook_proxy(request: Request) -> JSONResponse:
    """Receive Telegram updates on backend URL and forward to notification_service."""
    base_url = settings.notification_service_base_url
    if not base_url:
        logger.error("NOTIFICATION_SERVICE_BASE_URL is not configured")
        return JSONResponse({"detail": "Notification service base URL is not configured"}, status_code=503)

    target_url = f"{base_url.rstrip('/')}/webhooks/telegram"

    try:
        body = await request.body()
    except Exception:
        if _should_log_body_parse_error():
            logger.exception("Failed to read Telegram webhook request body")
        return JSONResponse({"status": "ok"}, status_code=200)

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            response = await client.post(
                target_url,
                content=body,
                headers=_build_forward_headers(request),
            )
    except Exception as exc:
        logger.error("Failed forwarding Telegram webhook to notification_service: %s", exc)
        return JSONResponse({"detail": "Failed forwarding Telegram webhook"}, status_code=502)

    try:
        data = response.json()
    except Exception:
        logger.error("Notification service returned non-JSON response for Telegram webhook")
        return JSONResponse({"detail": "Invalid response from notification service"}, status_code=502)

    return JSONResponse(data, status_code=response.status_code)
