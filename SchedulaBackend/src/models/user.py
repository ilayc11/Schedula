from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from src.models.base import SchedulaBaseModel


class UserRole(str, Enum):
    """User role enumeration"""
    LECTURER = "L"
    SECRETARY = "S"

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        schema = handler(core_schema)
        schema["example"] = "L"
        return schema


class UserBase(SchedulaBaseModel):
    """Base user model with common fields"""
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    role: UserRole
    department_id: int

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "first_name": "Dana",
                "last_name": "Levi",
                "email": "dana.levi@example.com",
                "role": "L",
                "department_id": 1
            }
        },
    }


class UserCreate(UserBase):
    """Model for creating a new user.

    Notification settings (phone_num, telegram, etc.) are NOT part of this
    payload; they live in the `user_notifications` table and are managed via
    the user notifications endpoints.
    """
    user_id: str = Field(..., min_length=9, max_length=9, description="Client-supplied user ID, external identifier")
    user_name: str = Field(..., min_length=1, max_length=255, description="Unique username for frontend")

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "user_id": "123456789",
                "user_name": "DLevi",
                "first_name": "Dana",
                "last_name": "Levi",
                "email": "dana.levi@example.com",
                "role": "L",
                "department_id": 1
            }
        },
    }


class UserUpdate(BaseModel):
    """Model for updating user information.

    Notification settings (phone_num, telegram, etc.) are managed separately
    via the user notifications endpoints and are not accepted here.
    """
    first_name: Optional[str] = Field(None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    department_id: Optional[int] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "first_name": "Daniel",
                "email": "daniel.levi@example.com"
            }
        }
    }


class UserResponse(UserBase):
    """Model for user responses sent to frontend"""
    user_name: str

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "first_name": "Dana",
                "last_name": "Levi",
                "email": "dana.levi@example.com",
                "role": "L",
                "department_id": 1,
                "user_name": "DLevi"
            }
        },
    }


class User(UserBase):
    """Complete user model for internal use, includes internal ID"""
    user_internal_id: int
    user_id: str
    user_name: str
    phone_num: Optional[str] = None

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "user_internal_id": 42,
                "user_id": "123456789",
                "user_name": "DLevi",
                "first_name": "Dana",
                "last_name": "Levi",
                "email": "dana.levi@example.com",
                "role": "L",
                "department_id": 1,
                "phone_num": "+972501234567"
            }
        },
    }
