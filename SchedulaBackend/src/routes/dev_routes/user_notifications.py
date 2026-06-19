"""DEV ONLY - User Notifications CRUD routes"""
from typing import List, Dict, Any
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from src.repositories import user_notifications
from src.models.user_notification import UserNotificationBase, UserNotificationInDB

router = APIRouter()


class ClearTelegramDataResponse(BaseModel):
    message: str
    affected_rows: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Cleared Telegram links and tokens for all users",
                "affected_rows": 12
            }
        }
    )

@router.get("/", response_model=List[UserNotificationInDB])
async def list_user_notifications() -> List[Dict[str, Any]]:
    """List all user notifications."""
    try:
        return await user_notifications.get_all()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{user_internal_id}", response_model=UserNotificationInDB)
async def get_user_notification(user_internal_id: int) -> Dict[str, Any]:
    """Get user notification by user_internal_id."""
    try:
        record = await user_notifications.get_by_user_id(user_internal_id)
        if not record:
            raise HTTPException(status_code=404, detail="User notification not found")
        return record
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", response_model=UserNotificationInDB, status_code=201)
async def create_or_update_user_notification(data: UserNotificationBase) -> Dict[str, Any]:
    """Create or update a user notification."""
    try:
        record = await user_notifications.upsert_user_notification(
            user_internal_id=data.user_internal_id, 
            data=data.model_dump(exclude={"user_internal_id"}, exclude_unset=True)
        )
        if not record:
            raise HTTPException(status_code=400, detail="Failed to create/update user notification")
        return record
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{notification_id}", status_code=204)
async def delete_user_notification(notification_id: int) -> None:
    """Delete user notification."""
    try:
        success = await user_notifications.delete_user_notification(notification_id)
        if not success:
            raise HTTPException(status_code=404, detail="User notification not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/clear-telegram-data", response_model=ClearTelegramDataResponse)
async def clear_all_telegram_data() -> ClearTelegramDataResponse:
    """DEV ONLY: Clear telegram_chat_id and telegram_token for all users."""
    try:
        affected_rows = await user_notifications.clear_all_telegram_data()
        return {
            "message": "Cleared Telegram links and tokens for all users",
            "affected_rows": affected_rows,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
