from typing import Dict, List, Optional, Any

from src.repositories.base import execute, fetch_all, fetch_one, update_row_returning, delete_row

TABLE = "courses_schedules"
ID_COL = "session_id"


async def create_course_schedule_upsert(
    offering_id: int, 
    lecturer_internal_id: int, 
    schedule_id: int,
    day_of_week: int,
    start_time: str,
    end_time: str
) -> Optional[Dict[str, Any]]:
    """Create or update a course session."""
    sql = (
        f"INSERT INTO {TABLE} (offering_id, lecturer_internal_id, schedule_id, day_of_week, start_time, end_time) "
        f"VALUES ($1, $2, $3, $4, $5, $6) "
        f"ON CONFLICT (offering_id, schedule_id, day_of_week, start_time) DO UPDATE SET "
        f"end_time = EXCLUDED.end_time, lecturer_internal_id = EXCLUDED.lecturer_internal_id "
        f"RETURNING *"
    )
    rec = await fetch_one(sql, offering_id, lecturer_internal_id, schedule_id, day_of_week, start_time, end_time)
    return dict(rec) if rec else None



async def list_sessions() -> List[Dict[str, Any]]:
    """Fetch all course sessions."""
    rows = await fetch_all(f"SELECT * FROM {TABLE} ORDER BY schedule_id, day_of_week, start_time")
    return [dict(r) for r in rows]


async def list_sessions_for_lecturer(lecturer_internal_id: int) -> List[Dict[str, Any]]:
    """Fetch all sessions for a specific lecturer."""
    rows = await fetch_all(
        f"SELECT * FROM {TABLE} WHERE lecturer_internal_id = $1 ORDER BY schedule_id, day_of_week, start_time",
        lecturer_internal_id
    )
    return [dict(r) for r in rows]


async def list_sessions_for_schedule(schedule_id: int) -> List[Dict[str, Any]]:
    """Fetch all sessions for a specific schedule."""
    rows = await fetch_all(
        f"SELECT * FROM {TABLE} WHERE schedule_id = $1 ORDER BY day_of_week, start_time",
        schedule_id
    )
    return [dict(r) for r in rows]


async def list_sessions_for_offering(offering_id: int) -> List[Dict[str, Any]]:
    """Fetch all sessions for a specific course offering."""
    rows = await fetch_all(
        f"SELECT * FROM {TABLE} WHERE offering_id = $1 ORDER BY schedule_id, day_of_week, start_time",
        offering_id
    )
    return [dict(r) for r in rows]


async def list_sessions_by_day(day_of_week: int) -> List[Dict[str, Any]]:
    """Fetch all sessions for a specific day of the week."""
    rows = await fetch_all(f"SELECT * FROM {TABLE} WHERE day_of_week = $1 ORDER BY schedule_id, start_time", day_of_week)
    return [dict(r) for r in rows]


async def list_sessions_by_start_time(start_time: str) -> List[Dict[str, Any]]:
    """Fetch all sessions starting at a specific time."""
    rows = await fetch_all(f"SELECT * FROM {TABLE} WHERE start_time = $1 ORDER BY schedule_id, day_of_week", start_time)
    return [dict(r) for r in rows]


async def list_sessions_by_end_time(end_time: str) -> List[Dict[str, Any]]:
    """Fetch all sessions ending at a specific time."""
    rows = await fetch_all(f"SELECT * FROM {TABLE} WHERE end_time = $1 ORDER BY schedule_id, day_of_week", end_time)
    return [dict(r) for r in rows]


async def get_session(session_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a single session by its internal ID."""
    rec = await fetch_one(f"SELECT * FROM {TABLE} WHERE {ID_COL} = $1", session_id)
    return dict(rec) if rec else None



async def update_session(session_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update a course session and return the updated object."""
    return await update_row_returning(TABLE, ID_COL, session_id, updates)



async def delete_session(session_id: int) -> bool:
    """Delete a session by its internal ID."""
    result = await delete_row(TABLE, ID_COL, session_id)
    return result.startswith("DELETE 1")


async def delete_all_for_schedule(schedule_id: int) -> bool:
    """Delete all sessions for a specific schedule."""
    sql = f"DELETE FROM {TABLE} WHERE schedule_id = $1"
    result = await execute(sql, schedule_id)
    return not result.startswith("DELETE 0")
