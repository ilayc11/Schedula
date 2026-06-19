from typing import Optional
from pydantic import BaseModel, Field, ConfigDict

from src.models.base import SchedulaBaseModel


PHONE_NUM_E164_PATTERN = r"^\+[1-9]\d{1,14}$"

class UserNotificationBase(SchedulaBaseModel):
    user_internal_id: int
    phone_num: Optional[str] = Field(None, max_length=20, pattern=PHONE_NUM_E164_PATTERN)
    telegram_chat_id: Optional[str] = Field(None, max_length=50)
    telegram_token: Optional[str] = Field(None, max_length=100)
    telegram_enabled: bool = True
    email_enabled: bool = True

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "user_internal_id": 42,
                "phone_num": "+972501234567",
                "telegram_chat_id": "123456789",
                "telegram_token": "abc123token",
                "telegram_enabled": True,
                "email_enabled": False
            }
        }
    )

class UserNotificationUpdate(BaseModel):
    phone_num: Optional[str] = Field(None, max_length=20, pattern=PHONE_NUM_E164_PATTERN)
    telegram_chat_id: Optional[str] = Field(None, max_length=50)
    telegram_token: Optional[str] = Field(None, max_length=100)
    telegram_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "telegram_enabled": True,
                "email_enabled": False
            }
        }
    )

class UserNotificationInDB(UserNotificationBase):
    notification_id: int

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "notification_id": 21,
                "user_internal_id": 42,
                "phone_num": "+972501234567",
                "telegram_chat_id": "123456789",
                "telegram_token": "abc123token",
                "telegram_enabled": True,
                "email_enabled": False
            }
        }
    )
