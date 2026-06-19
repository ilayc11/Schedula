from typing import Dict, List, Optional, Any

from src.database.database import db
from src.repositories.base import fetch_one, fetch_all, delete_row

TABLE = "users"
ID_COL = "user_internal_id"
PHONE_COL = "phone_num"

BASE_SELECT_WITH_PHONE = f"""
    SELECT u.*, un.{PHONE_COL}
    FROM {TABLE} u
    LEFT JOIN user_notifications un ON un.user_internal_id = u.{ID_COL}
"""


async def _sync_phone_in_tx(conn: Any, user_internal_id: int, phone_num: Optional[str]) -> None:
    """Persist phone in user_notifications while preserving existing notification channel fields."""
    if phone_num is None:
        await conn.execute(
            """
            UPDATE user_notifications
            SET phone_num = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE user_internal_id = $1
            """,
            user_internal_id,
        )
        return

    await conn.execute(
        """
        INSERT INTO user_notifications (user_internal_id, phone_num, updated_at)
        VALUES ($1, $2, CURRENT_TIMESTAMP)
        ON CONFLICT (user_internal_id)
        DO UPDATE SET
            phone_num = EXCLUDED.phone_num,
            updated_at = CURRENT_TIMESTAMP
        """,
        user_internal_id,
        phone_num,
    )


async def create_user(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Create a new user and return the full object."""
    if "user_name" not in data or not isinstance(data.get("user_name"), str) or not data.get("user_name"):
        raise ValueError("user_name must be provided and non-empty")

    payload = data.copy()
    phone_provided = PHONE_COL in payload
    phone_num = payload.pop(PHONE_COL, None)

    async with db.transaction() as conn:
        columns = ", ".join(payload.keys())
        placeholders = ", ".join([f"${i}" for i in range(1, len(payload) + 1)])
        insert_sql = f"INSERT INTO {TABLE} ({columns}) VALUES ({placeholders}) RETURNING *"
        created_user = await conn.fetchrow(insert_sql, *payload.values())
        if not created_user:
            return None

        user_internal_id = int(created_user[ID_COL])
        if phone_provided:
            await _sync_phone_in_tx(conn, user_internal_id, phone_num)

        full_row = await conn.fetchrow(
            f"{BASE_SELECT_WITH_PHONE} WHERE u.{ID_COL} = $1",
            user_internal_id,
        )
        return dict(full_row) if full_row else None


async def get_user_by_internal_id(user_internal_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a single user by internal DB ID"""
    sql = f"{BASE_SELECT_WITH_PHONE} WHERE u.{ID_COL} = $1"
    rec = await fetch_one(sql, user_internal_id)
    return dict(rec) if rec else None


async def get_user_by_name(user_name: str) -> Optional[Dict[str, Any]]:
    """Fetch a single user by unique username"""
    sql = f"{BASE_SELECT_WITH_PHONE} WHERE u.user_name = $1"
    rec = await fetch_one(sql, user_name)
    return dict(rec) if rec else None


async def get_user_by_user_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Fetch a single user by unique user_id."""
    sql = f"{BASE_SELECT_WITH_PHONE} WHERE u.user_id = $1"
    rec = await fetch_one(sql, user_id)
    return dict(rec) if rec else None


async def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Fetch a single user by unique email"""
    sql = f"{BASE_SELECT_WITH_PHONE} WHERE u.email = $1"
    rec = await fetch_one(sql, email)
    return dict(rec) if rec else None


async def list_users() -> List[Dict[str, Any]]:
    """Fetch all users"""
    rows = await fetch_all(BASE_SELECT_WITH_PHONE)
    return [dict(r) for r in rows]


async def list_users_by_role(role: str) -> List[Dict[str, Any]]:
    """Fetch all users with a specific role"""
    sql = f"{BASE_SELECT_WITH_PHONE} WHERE u.role = $1"
    rows = await fetch_all(sql, role)
    return [dict(r) for r in rows]


async def list_users_by_department(department_id: int) -> List[Dict[str, Any]]:
    """Fetch all users in a specific department"""
    sql = f"{BASE_SELECT_WITH_PHONE} WHERE u.department_id = $1"
    rows = await fetch_all(sql, department_id)
    return [dict(r) for r in rows]


async def update_user(user_internal_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update a user and return the updated object."""
    payload = updates.copy()
    phone_provided = PHONE_COL in payload
    phone_num = payload.pop(PHONE_COL, None)

    async with db.transaction() as conn:
        if payload:
            set_clause = ", ".join([f"{col} = ${i}" for i, col in enumerate(payload.keys(), start=1)])
            update_sql = (
                f"UPDATE {TABLE} SET {set_clause} "
                f"WHERE {ID_COL} = ${len(payload) + 1} RETURNING {ID_COL}"
            )
            updated_row = await conn.fetchrow(update_sql, *payload.values(), user_internal_id)
            if not updated_row:
                return None
        else:
            existing = await conn.fetchrow(
                f"SELECT {ID_COL} FROM {TABLE} WHERE {ID_COL} = $1",
                user_internal_id,
            )
            if not existing:
                return None

        if phone_provided:
            await _sync_phone_in_tx(conn, user_internal_id, phone_num)

        full_row = await conn.fetchrow(
            f"{BASE_SELECT_WITH_PHONE} WHERE u.{ID_COL} = $1",
            user_internal_id,
        )
        return dict(full_row) if full_row else None


async def delete_user(user_internal_id: int) -> bool:
    """Delete a user by internal DB ID."""
    result = await delete_row(TABLE, ID_COL, user_internal_id)
    return result.startswith("DELETE 1")
