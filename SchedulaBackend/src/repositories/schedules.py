from typing import Dict, List, Optional, Any

from src.repositories.base import execute, fetch_one, fetch_all, update_row_returning, delete_row

TABLE = "schedules"
ID_COL = "schedule_id"
TABLE_SESSIONS = "courses_schedules"

async def create_schedule(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Insert a new schedule record and return the full created object (using RETURNING *).
    """
    cols = ", ".join(data.keys())
    placeholders = ", ".join([f"${i}" for i in range(1, len(data) + 1)])

    # Use RETURNING * to fetch the full row, including auto-generated schedule_id and timestamps
    sql = f"INSERT INTO {TABLE} ({cols}) VALUES ({placeholders}) RETURNING *"

    rec = await fetch_one(sql, *data.values())

    return dict(rec) if rec else None


async def get_schedule(schedule_id: int) -> Optional[Dict[str, Any]]:
    """Return a single schedule by its primary key."""
    rec = await fetch_one(f"SELECT * FROM {TABLE} WHERE {ID_COL} = $1", schedule_id)
    return dict(rec) if rec else None


async def list_by_semester(year: int, number: int) -> List[Dict[str, Any]]:
    """Returns all schedules for a specific semester."""
    rows = await fetch_all(
        f"SELECT * FROM {TABLE} WHERE semester_year = $1 AND semester_number = $2",
        year,
        number,
    )
    return [dict(r) for r in rows]


async def list_all_schedules() -> List[Dict[str, Any]]:
    """Returns all schedules."""
    rows = await fetch_all(f"SELECT * FROM {TABLE} ORDER BY schedule_id DESC")
    return [dict(r) for r in rows]


async def update_schedule(schedule_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update a schedule and return the updated object."""
    return await update_row_returning(TABLE, ID_COL, schedule_id, updates)


async def update_and_get_schedule(schedule_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update a schedule record and return the updated object (alias for consistency)."""
    return await update_schedule(schedule_id, updates)

async def delete_schedule(schedule_id: int) -> bool:
    """Delete a schedule by its ID."""
    result = await delete_row(TABLE, ID_COL, schedule_id)
    return result.startswith("DELETE 1")


async def get_latest_schedule_for_semester(year: int, number: int) -> Optional[Dict[str, Any]]:
    """
    Returns the most recently created schedule for a specific semester.
    Useful for dashboards and quick status checks.
    """
    sql = f"""
        SELECT * FROM {TABLE} 
        WHERE semester_year = $1 AND semester_number = $2 
        ORDER BY schedule_id DESC 
        LIMIT 1
    """
    rec = await fetch_one(sql, year, number)
    return dict(rec) if rec else None


async def find_empty_draft_for_semester(
    year: int, number: int
) -> Optional[Dict[str, Any]]:
    """Return the most recent draft schedule for the semester that has no
    sessions in ``courses_schedules``, or ``None``.

    Used by ``POST /secretary/schedules/publish_request`` to avoid inserting
    a fresh ``schedules`` row every time the secretary triggers a solve when
    the previous run failed (or has not written yet) and left a draft with
    no sessions. Reusing the draft means the ``schedule_id`` returned to the
    API caller is the same row the solver will write its sessions to, so
    ``get_latest_schedule_for_semester`` reflects the current solution.
    """
    sql = f"""
        SELECT s.* FROM {TABLE} s
        WHERE s.semester_year = $1
          AND s.semester_number = $2
          AND s.is_draft = TRUE
          AND s.is_published = FALSE
          AND NOT EXISTS (
              SELECT 1 FROM {TABLE_SESSIONS} cs
              WHERE cs.schedule_id = s.schedule_id
          )
        ORDER BY s.schedule_id DESC
        LIMIT 1
    """
    rec = await fetch_one(sql, year, number)
    return dict(rec) if rec else None


async def upsert_manual_session(schedule_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Creates a new session or updates an existing one for a specific offering in a schedule.
    This is used for manual overrides by the secretary.
    """

    # We check if this offering already has a session in this schedule
    check_sql = f"""
        SELECT session_id FROM {TABLE_SESSIONS} 
        WHERE schedule_id = $1 AND offering_id = $2
    """
    existing_session = await fetch_one(check_sql, schedule_id, data['offering_id'])

    if existing_session:
        sql = f"""
            UPDATE {TABLE_SESSIONS}
            SET 
                lecturer_internal_id = $2,
                day_of_week = $3,
                start_time = $4,
                end_time = $5
            WHERE session_id = $1
            RETURNING *
        """
        result = await fetch_one(
            sql,
            existing_session['session_id'],
            data['lecturer_internal_id'],
            data['day_of_week'],
            data['start_time'],
            data['end_time']
        )
    else:
        # INSERT new session
        sql = f"""
            INSERT INTO {TABLE_SESSIONS} (
                schedule_id, offering_id, lecturer_internal_id, 
                day_of_week, start_time, end_time
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *
        """
        result = await fetch_one(
            sql,
            schedule_id,
            data['offering_id'],
            data['lecturer_internal_id'],
            data['day_of_week'],
            data['start_time'],
            data['end_time']
        )

    return dict(result) if result else None


async def delete_session(schedule_id: int, session_id: int) -> bool:
    """
    Deletes a specific session from a schedule.
    """
    sql = f"DELETE FROM {TABLE_SESSIONS} WHERE schedule_id = $1 AND session_id = $2 RETURNING session_id"
    result = await fetch_one(sql, schedule_id, session_id)
    return result is not None