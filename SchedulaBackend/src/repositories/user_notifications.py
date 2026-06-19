from typing import Dict, Optional, Any
from datetime import datetime, timezone

from src.repositories.base import execute, fetch_one, fetch_all, insert_row_returning, update_row_returning

TABLE = "user_notifications"
ID_COL = "notification_id"

async def get_by_user_id(user_internal_id: int) -> Optional[Dict[str, Any]]:
    """Fetch user notification settings by user internal ID."""
    sql = f"SELECT * FROM {TABLE} WHERE user_internal_id = $1"
    rec = await fetch_one(sql, user_internal_id)
    return dict(rec) if rec else None

async def get_by_telegram_token(token: str) -> Optional[Dict[str, Any]]:
    """Fetch user notification settings by telegram token."""
    sql = f"SELECT * FROM {TABLE} WHERE telegram_token = $1"
    rec = await fetch_one(sql, token)
    return dict(rec) if rec else None

async def upsert_user_notification(user_internal_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update or insert user notification settings."""
    existing = await get_by_user_id(user_internal_id)
    if existing:
        updates = {k: v for k, v in data.items() if k != "user_internal_id"}
        if not updates:
            return existing
        updates["updated_at"] = datetime.now(timezone.utc)
        
        # We need a custom update since the base.py `update_row_returning` uses primary key.
        # So we use the notification_id
        return await update_row_returning(TABLE, ID_COL, existing[ID_COL], updates)
    else:
        insert_data = {"user_internal_id": user_internal_id, **data}
        return await insert_row_returning(TABLE, insert_data)

async def update_by_token(token: str, telegram_chat_id: str) -> bool:
    """Update telegram chat ID using token directly, typically strictly for webhook."""
    existing = await get_by_telegram_token(token)
    if not existing:
        return False

    existing_chat_id = existing.get("telegram_chat_id")
    if existing_chat_id is not None and str(existing_chat_id) == telegram_chat_id:
        return True

    updates = {
        "telegram_chat_id": telegram_chat_id,
        "telegram_enabled": True,
        "updated_at": datetime.now(timezone.utc),
    }
    updated = await update_row_returning(TABLE, ID_COL, existing[ID_COL], updates)
    return bool(updated)

async def get_all() -> list[Dict[str, Any]]:
    """Fetch all user notifications."""
    sql = f"SELECT * FROM {TABLE}"
    records = await fetch_all(sql)
    return [dict(rec) for rec in records]

async def delete_user_notification(notification_id: int) -> bool:
    """Delete a user notification by ID."""
    sql = f"DELETE FROM {TABLE} WHERE {ID_COL} = $1"
    result = await execute(sql, notification_id)

    if isinstance(result, int):
        return result > 0

    if isinstance(result, str):
        # asyncpg execute returns status strings like "DELETE 0" or "DELETE 1"
        parts = result.strip().split()
        if len(parts) >= 2 and parts[0].upper() == "DELETE":
            try:
                return int(parts[-1]) > 0
            except ValueError:
                return False

    return False


async def clear_all_telegram_data() -> int:
    """Clear all Telegram linking data for all users and return affected rows."""
    sql = f"""
        UPDATE {TABLE}
        SET
            telegram_chat_id = NULL,
            telegram_token = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE telegram_chat_id IS NOT NULL OR telegram_token IS NOT NULL
        RETURNING {ID_COL}
    """
    rows = await fetch_all(sql)
    return len(rows)
