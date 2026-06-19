"""DEV ONLY - Users CRUD routes

Note: notification settings (phone_num, telegram_*, email_enabled) are not
exposed here. Manage them via /dev/user-notifications/ instead.
"""
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Body

from src.repositories import users
from src.models.user import UserCreate, UserUpdate


router = APIRouter()

# Fields that belong to user_notifications and must not be returned by /dev/users/
# Fields that belong to user_notifications and must not be returned by /dev/users/
_NOTIFICATION_FIELDS = {"phone_num"}
_INTERNAL_FIELDS: set[str] = set()


def _public_user(record: Dict[str, Any]) -> Dict[str, Any]:
    """Strip internal-only and notification-table fields from a user row."""
    excluded = _INTERNAL_FIELDS | _NOTIFICATION_FIELDS
    return {k: v for k, v in record.items() if k not in excluded}


@router.post(
    "/",
    status_code=201,
    responses={
        201: {
            "description": "User created",
            "content": {
                "application/json": {
                    "example": {
                        "user_name": "johnd",
                        "first_name": "John",
                        "last_name": "Doe",
                        "email": "john@example.com",
                        "role": "L",
                        "department_id": 202,
                    }
                }
            },
        },
        400: {"description": "Invalid data", "content": {"application/json": {"example": {"detail": "Invalid data"}}}},
        422: {"description": "Validation error"},
    },
)
async def create_user(
    payload: UserCreate = Body(
        ...,
        examples=[{
            "user_id": "123456789",
            "user_name": "johnd",
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "role": "L",
            "department_id": 202,
        }],
    )
) -> Dict[str, object]:
    """Create a new user (client supplies user_id).

    To set phone/telegram/email notification preferences, use
    POST /dev/user-notifications/ after creating the user.
    """
    try:
        data = payload.model_dump()
        result = await users.create_user(data)
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create user")
        return _public_user(result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/{user_name}",
    responses={
        200: {
            "description": "User found",
            "content": {
                "application/json": {
                    "example": {
                        "user_name": "johnd",
                        "first_name": "John",
                        "last_name": "Doe",
                        "email": "john@example.com",
                        "role": "L",
                        "department_id": 202,
                    }
                }
            },
        },
        404: {"description": "User not found", "content": {"application/json": {"example": {"detail": "User not found"}}}},
    },
)
async def get_user(user_name: str) -> Dict[str, object]:
    """Get user by user_name (unique identifier for frontend)"""
    user = await users.get_user_by_name(user_name)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _public_user(user)


@router.get(
    "/email/{email}",
    responses={
        200: {
            "description": "User found",
            "content": {
                "application/json": {
                    "example": {
                        "user_name": "johnd",
                        "first_name": "John",
                        "last_name": "Doe",
                        "email": "john@example.com",
                        "role": "L",
                        "department_id": 202,
                    }
                }
            },
        },
        404: {"description": "User not found", "content": {"application/json": {"example": {"detail": "User not found"}}}},
    },
)
async def get_user_by_email(email: str) -> Dict[str, object]:
    """Get user by email"""
    user = await users.get_user_by_email(email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return _public_user(user)


@router.get(
    "/",
    responses={
        200: {
            "description": "List of users",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "user_name": "johnd",
                            "first_name": "John",
                            "last_name": "Doe",
                            "email": "john@example.com",
                            "role": "L",
                            "department_id": 202,
                        }
                    ]
                }
            },
        }
    },
)
async def list_users() -> List[Dict[str, object]]:
    """List all users"""
    users_list = await users.list_users()
    return [_public_user(u) for u in users_list]


@router.patch(
    "/{user_name}",
    responses={
        200: {
            "description": "User updated",
            "content": {"application/json": {"example": {
                "user_name": "johnd",
                "first_name": "John",
                "last_name": "Doe",
                "email": "john@example.com",
                "role": "L",
                "department_id": 202,
            }}},
        },
        400: {
            "description": "Invalid update data",
            "content": {"application/json": {"example": {"detail": "Invalid update data"}}},
        },
    },
)
async def update_user(user_name: str, updates: UserUpdate) -> Dict[str, object]:
    """Update user fields by user_name.

    Notification settings are not accepted here; use /dev/user-notifications/.
    """
    try:
        user = await users.get_user_by_name(user_name)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        result = await users.update_user(user["user_internal_id"], updates.model_dump(exclude_unset=True))
        if not result:
            raise HTTPException(status_code=404, detail="User not found or update failed")
        return _public_user(result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/{user_name}",
    status_code=204,
    responses={
        204: {
            "description": "User deleted successfully",
        },
        400: {
            "description": "Deletion failed",
            "content": {"application/json": {"example": {"detail": "Deletion failed"}}},
        },
    },
)
async def delete_user(user_name: str) -> None:
    """Delete a user by user_name"""
    try:
        user = await users.get_user_by_name(user_name)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        success = await users.delete_user(user["user_internal_id"])
        if not success:
            raise HTTPException(status_code=404, detail="User not found or delete failed")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
