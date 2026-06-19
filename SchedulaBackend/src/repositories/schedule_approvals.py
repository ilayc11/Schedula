from typing import Dict, List, Optional, Any

from src.repositories.base import execute, fetch_one, fetch_all, update_row_returning, delete_row, upsert_row_returning

TABLE = "schedule_approvals"
ID_COL = "scheapprov_id"


async def create_schedule_approval_upsert(schedule_id: int, lecturer_internal_id: int, status: str) -> Optional[Dict[str, Any]]:
    """Create or update approval status based on unique key (schedule_id, lecturer_internal_id)."""
    data = {
        "schedule_id": schedule_id,
        "lecturer_internal_id": lecturer_internal_id,
        "status": status
    }
    return await upsert_row_returning(TABLE, ["schedule_id", "lecturer_internal_id"], data)


async def get_approval(scheapprov_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a single approval by its internal ID."""
    rec = await fetch_one(f"SELECT * FROM {TABLE} WHERE {ID_COL} = $1", scheapprov_id)
    return dict(rec) if rec else None


async def list_all_approvals() -> List[Dict[str, Any]]:
    """Fetch all schedule approvals."""
    rows = await fetch_all(f"SELECT * FROM {TABLE} ORDER BY schedule_id, lecturer_internal_id")
    return [dict(r) for r in rows]


async def list_approvals_by_lecturer(lecturer_internal_id: int) -> List[Dict[str, Any]]:
    """Fetch all approvals submitted by a specific lecturer."""
    rows = await fetch_all(
        f"SELECT * FROM {TABLE} WHERE lecturer_internal_id = $1 ORDER BY schedule_id DESC",
        lecturer_internal_id
    )
    return [dict(r) for r in rows]


async def list_approvals_for_schedule(schedule_id: int) -> List[Dict[str, Any]]:
    """Fetch all approvals for a specific schedule."""
    rows = await fetch_all(f"SELECT * FROM {TABLE} WHERE schedule_id = $1", schedule_id)
    return [dict(r) for r in rows]


async def get_user_approval(schedule_id: int, lecturer_internal_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a single approval for a specific schedule and lecturer."""
    rec = await fetch_one(
        f"SELECT * FROM {TABLE} WHERE schedule_id = $1 AND lecturer_internal_id = $2",
        schedule_id,
        lecturer_internal_id,
    )
    return dict(rec) if rec else None


async def list_all_by_status(status: str) -> List[Dict[str, Any]]:
    """Fetch all approvals across all schedules with a specific status."""
    rows = await fetch_all(
        f"SELECT * FROM {TABLE} WHERE status = $1 ORDER BY schedule_id",
        status
    )
    return [dict(r) for r in rows]


async def list_approvals_by_schedule_and_status(schedule_id: int, status: str) -> List[Dict[str, Any]]:
    """Fetch all approvals for a schedule with a specific status."""
    rows = await fetch_all(
        f"SELECT * FROM {TABLE} WHERE schedule_id = $1 AND status = $2",
        schedule_id,
        status
    )
    return [dict(r) for r in rows]


async def list_schedules_by_user_and_status(lecturer_internal_id: int, status: str) -> List[Dict[str, Any]]:
    """Fetch all schedules where the lecturer has a specific status."""
    rows = await fetch_all(
        f"SELECT * FROM {TABLE} WHERE lecturer_internal_id = $1 AND status = $2",
        lecturer_internal_id,
        status
    )
    return [dict(r) for r in rows]


async def update_approval(scheapprov_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update approval and return the updated object."""
    return await update_row_returning(TABLE, ID_COL, scheapprov_id, updates)


async def delete_approval(scheapprov_id: int) -> bool:
    """Delete approval by its internal ID."""
    result = await delete_row(TABLE, ID_COL, scheapprov_id)
    return result.startswith("DELETE 1")


