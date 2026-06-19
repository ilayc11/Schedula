from typing import Any, Dict, Optional

from src.db import db


async def get_by_user_id(user_internal_id: int) -> Optional[Dict[str, Any]]:
    """Fetch user notification settings by user internal ID."""
    sql = """
        SELECT *
        FROM user_notifications
        WHERE user_internal_id = $1
    """
    record = await db.fetch_one(sql, int(user_internal_id))
    return dict(record) if record else None


async def user_exists(user_internal_id: int) -> bool:
    """Return whether a user exists for the given internal ID."""
    sql = """
        SELECT 1
        FROM users
        WHERE user_internal_id = $1
    """
    record = await db.fetch_one(sql, int(user_internal_id))
    return bool(record)


async def set_link_token(user_internal_id: int, token: str) -> Optional[Dict[str, Any]]:
    """Create or update a Telegram link token for a user and return notification row."""
    sql = """
        INSERT INTO user_notifications (
            user_internal_id,
            telegram_token,
            telegram_enabled,
            updated_at
        )
        VALUES ($1, $2, TRUE, CURRENT_TIMESTAMP)
        ON CONFLICT (user_internal_id)
        DO UPDATE SET
            telegram_token = EXCLUDED.telegram_token,
            telegram_enabled = TRUE,
            updated_at = CURRENT_TIMESTAMP
        RETURNING *
    """
    record = await db.fetch_one(sql, int(user_internal_id), token)
    return dict(record) if record else None


async def get_delivery_profiles_for_users(user_internal_ids: list[int]) -> dict[int, Dict[str, Any]]:
    """Return notification delivery profiles keyed by user_internal_id.

    Includes notification-owned profile data such as phone_num and Telegram settings.
    """
    if not user_internal_ids:
        return {}

    normalized_values: list[int] = []
    for raw_user_id in user_internal_ids:
        try:
            user_id = int(raw_user_id)
        except (TypeError, ValueError):
            continue

        if user_id > 0:
            normalized_values.append(user_id)

    normalized_ids = sorted(set(normalized_values))
    if not normalized_ids:
        return {}

    sql = """
        SELECT
            u.user_internal_id,
            u.email,
            un.phone_num,
            un.telegram_chat_id,
            COALESCE(un.telegram_enabled, FALSE) AS telegram_enabled,
            COALESCE(un.email_enabled, TRUE) AS email_enabled
        FROM users u
        LEFT JOIN user_notifications un ON un.user_internal_id = u.user_internal_id
        WHERE u.user_internal_id = ANY($1::bigint[])
    """
    rows = await db.fetch_all(sql, normalized_ids)

    result: dict[int, Dict[str, Any]] = {}
    for row in rows:
        payload = dict(row)
        result[int(payload["user_internal_id"])] = payload

    return result


async def link_chat_by_token(token: str, chat_id: str, max_age_seconds: int | None = None) -> Dict[str, Any]:
    """Link Telegram chat by deep-link token with optional token TTL validation."""
    if max_age_seconds is not None and max_age_seconds <= 0:
        return {
            "success": False,
            "message": "Invalid or expired token",
            "user_internal_id": None,
        }

    if max_age_seconds is None:
        update_sql = """
            UPDATE user_notifications
            SET
                telegram_chat_id = $1,
                telegram_token = NULL,
                telegram_enabled = TRUE,
                updated_at = CURRENT_TIMESTAMP
            WHERE telegram_token = $2
            RETURNING user_internal_id
        """
        updated = await db.fetch_one(update_sql, chat_id, token)
    else:
        update_sql = """
            UPDATE user_notifications
            SET
                telegram_chat_id = $1,
                telegram_token = NULL,
                telegram_enabled = TRUE,
                updated_at = CURRENT_TIMESTAMP
            WHERE telegram_token = $2
              AND COALESCE(updated_at, created_at) >= (CURRENT_TIMESTAMP - ($3::int * INTERVAL '1 second'))
            RETURNING user_internal_id
        """
        updated = await db.fetch_one(update_sql, chat_id, token, int(max_age_seconds))

    if not updated:
        return {
            "success": False,
            "message": "Failed to link Telegram chat",
            "user_internal_id": None,
        }

    user_internal_id = int(updated["user_internal_id"])
    return {
        "success": True,
        "message": "Telegram linked successfully",
        "user_internal_id": user_internal_id,
    }


async def link_chat_by_credentials(user_name: str, user_id: str, chat_id: str) -> Dict[str, Any]:
    """Link Telegram chat by fallback credentials flow."""
    user_sql = """
        SELECT user_internal_id
        FROM users
        WHERE user_name = $1 AND user_id = $2
    """
    user_record = await db.fetch_one(user_sql, user_name, user_id)
    if not user_record:
        return {
            "success": False,
            "message": "Invalid credentials",
            "user_internal_id": None,
        }

    user_internal_id = int(user_record["user_internal_id"])

    upsert_sql = """
        INSERT INTO user_notifications (
            user_internal_id,
            telegram_chat_id,
            telegram_token,
            telegram_enabled,
            updated_at
        )
        VALUES ($1, $2, NULL, TRUE, CURRENT_TIMESTAMP)
        ON CONFLICT (user_internal_id)
        DO UPDATE SET
            telegram_chat_id = EXCLUDED.telegram_chat_id,
            telegram_token = NULL,
            telegram_enabled = TRUE,
            updated_at = CURRENT_TIMESTAMP
        RETURNING user_internal_id
    """
    linked = await db.fetch_one(upsert_sql, user_internal_id, chat_id)
    if not linked:
        return {
            "success": False,
            "message": "Failed to link Telegram chat",
            "user_internal_id": None,
        }

    return {
        "success": True,
        "message": "Telegram linked successfully",
        "user_internal_id": user_internal_id,
    }
