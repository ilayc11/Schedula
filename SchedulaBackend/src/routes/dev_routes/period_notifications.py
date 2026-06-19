"""DEV ONLY - Period notification preview/send delegation routes"""
import logging
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ConfigDict

from src.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


class PeriodNotificationRequest(BaseModel):
    semester_year: int
    semester_number: int
    period_type: str = Field(..., pattern="^(constraint|change|status)$")
    transition_type: str = Field(..., pattern="^(start|ending_soon|ended|changed)$")
    warning_hours: int | None = None
    transition_date: str | None = None
    old_status: str | None = None
    new_status: str | None = None
    recipient_user_ids: list[int] = Field(default_factory=list)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "semester_year": 2026,
                "semester_number": 1,
                "period_type": "constraint",
                "transition_type": "ending_soon",
                "warning_hours": 24,
                "transition_date": "2026-11-09",
                "recipient_user_ids": [42, 56]
            }
        }
    )


class PeriodNotificationPreviewResponse(BaseModel):
    title: str
    body: str
    metadata: dict[str, Any]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "Constraint submission period ending soon",
                "body": "Constraint submission period for semester 2026/1 ends in about 24 hours.",
                "metadata": {
                    "event_type": "period_transition",
                    "semester_year": 2026,
                    "semester_number": 1,
                    "period_type": "constraint",
                    "transition_type": "ending_soon",
                    "warning_hours": 24
                }
            }
        }
    )


class PeriodNotificationSendResponse(BaseModel):
    requested: int
    attempted: int
    delivered: int
    title: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "requested": 2,
                "attempted": 2,
                "delivered": 1,
                "title": "Constraint submission period ending soon"
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


async def _delegate_period_request(
    route_path: str,
    *,
    payload: dict[str, Any],
    error_message: str,
) -> dict[str, Any]:
    target_url = f"{_notification_base_url()}{route_path}"

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            response = await client.post(target_url, json=payload)
    except Exception as exc:
        logger.error("Failed calling notification_service endpoint %s: %s", route_path, exc)
        raise HTTPException(status_code=502, detail="Failed contacting notification service")

    if response.status_code != 200:
        detail = _extract_error_detail(response, error_message)
        raise HTTPException(status_code=response.status_code, detail=detail)

    return response.json()


@router.post("/preview", response_model=PeriodNotificationPreviewResponse)
async def preview_period_notification(payload: PeriodNotificationRequest) -> PeriodNotificationPreviewResponse:
    response_data = await _delegate_period_request(
        "/internal/period-notifications/preview",
        payload=payload.model_dump(exclude_none=True),
        error_message="Notification service failed to preview period notification",
    )
    return PeriodNotificationPreviewResponse.model_validate(response_data)


@router.post("/send", response_model=PeriodNotificationSendResponse)
async def send_period_notification(payload: PeriodNotificationRequest) -> PeriodNotificationSendResponse:
    response_data = await _delegate_period_request(
        "/internal/period-notifications/send",
        payload=payload.model_dump(exclude_none=True),
        error_message="Notification service failed to send period notification",
    )
    return PeriodNotificationSendResponse.model_validate(response_data)
