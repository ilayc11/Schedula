import json
from typing import Dict, List, Optional, Any

from src.repositories.base import execute, fetch_one, fetch_all

TABLE = "breaking_constraints"
ID_COL = "breaking_id"


def _parse_json_fields(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse JSON string fields from psycopg2 into Python objects.
    
    Args:
        record: Dictionary containing potential JSON string fields
        
    Returns:
        Dictionary with parsed JSON fields
    """
    parsed = record.copy()

    for field in ("breaking_atomic_constraints", "structured_rules"):
        value = parsed.get(field)
        if isinstance(value, str):
            try:
                parsed[field] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                pass

    return parsed


async def clear_by_semester(year: int, number: int) -> int:
    """
    Clear all breaking constraints for a specific semester.
    Returns the number of rows deleted.
    """
    sql = f"DELETE FROM {TABLE} WHERE semester_year = $1 AND semester_number = $2"
    result = await execute(sql, year, number)
    # Result format is "DELETE N" where N is the number of deleted rows
    if result and result.startswith("DELETE"):
        return int(result.split()[-1])
    return 0


async def create_breaking_constraints(constraints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Bulk insert breaking constraints.
    
    Args:
        constraints: List of dicts with keys: constraints_id, atomic_constraint_index,
                     semester_year, semester_number
    
    Returns:
        List of created breaking constraint records
    """
    if not constraints:
        return []
    
    # Build INSERT statement with multiple values
    sql = f"""
        INSERT INTO {TABLE} (constraints_id, atomic_constraint_index, semester_year, semester_number)
        VALUES ($1, $2, $3, $4)
        RETURNING *
    """
    
    created = []
    for constraint in constraints:
        rec = await fetch_one(
            sql,
            constraint['constraints_id'],
            constraint['atomic_constraint_index'],
            constraint['semester_year'],
            constraint['semester_number']
        )
        if rec:
            created.append(dict(rec))
    
    return created


async def list_all() -> List[Dict[str, Any]]:
    """
    Get all breaking constraints across all semesters.
    
    Returns:
        List of all breaking constraints with grouped atomic constraints:
        - breaking_id: Unique ID for this breaking constraint entry
        - constraints_id: Reference to the full constraint in lecturer_constraints table
        - breaking_atomic_constraints: Array of breaking atomic constraints
        - lecturer_internal_id: Reference to the lecturer
        - raw_text: The original constraint text from lecturer_constraints
        - semester_year, semester_number: Semester information
        - is_seen: Whether the constraint has been seen by secretary
        - created_at: Timestamp
    """
    sql = f"""
        SELECT 
            bc.breaking_id,
            bc.constraints_id,
            bc.breaking_atomic_constraints,
            bc.semester_year,
            bc.semester_number,
            bc.is_seen,
            bc.created_at,
            lc.lecturer_internal_id,
            lc.raw_text,
            lc.structured_rules,
            lc.is_manually_edited,
            lc.original_raw_text
        FROM {TABLE} bc
        JOIN lecturer_constraints lc ON bc.constraints_id = lc.constraints_id
        ORDER BY bc.created_at DESC
    """
    
    rows = await fetch_all(sql)
    return [_parse_json_fields(dict(r)) for r in rows]


async def list_by_semester(year: int, number: int, unseen_only: bool = False) -> List[Dict[str, Any]]:
    """
    Get all breaking constraints for a semester (grouped by constraints_id).
    
    Args:
        year: Semester year
        number: Semester number
        unseen_only: If True, only return constraints where is_seen = False
    
    Returns:
        List of breaking constraints with grouped atomic constraints:
        - breaking_id: Unique ID for this breaking constraint entry
        - constraints_id: Reference to the full constraint in lecturer_constraints table
        - breaking_atomic_constraints: Array of breaking atomic constraints, each with:
            - atomic_constraint_index: Index in the original constraint
            - days: Array of day numbers
            - type: Constraint type (usually "block")
            - time_slot: {start_hour, end_hour}
        - lecturer_internal_id: Reference to the lecturer
        - raw_text: The original constraint text from lecturer_constraints
        - Timestamps and metadata
    """
    where_clause = "bc.semester_year = $1 AND bc.semester_number = $2"
    if unseen_only:
        where_clause += " AND bc.is_seen = FALSE"
    
    sql = f"""
        SELECT 
            bc.breaking_id,
            bc.constraints_id,
            bc.breaking_atomic_constraints,
            bc.semester_year,
            bc.semester_number,
            bc.is_seen,
            bc.created_at,
            lc.lecturer_internal_id,
            lc.raw_text,
            lc.structured_rules,
            lc.is_manually_edited,
            lc.original_raw_text
        FROM {TABLE} bc
        JOIN lecturer_constraints lc ON bc.constraints_id = lc.constraints_id
        WHERE {where_clause}
        ORDER BY bc.created_at DESC
    """
    
    rows = await fetch_all(sql, year, number)
    return [_parse_json_fields(dict(r)) for r in rows]


async def list_by_schedule(schedule_id: int) -> List[Dict[str, Any]]:
    """
    Get all breaking constraints for a schedule (grouped by constraints_id).
    
    Args:
        schedule_id: Schedule ID
    
    Returns:
        List of breaking constraints with grouped atomic constraints:
        - breaking_id: Unique ID for this breaking constraint entry
        - constraints_id: Reference to the full constraint in lecturer_constraints table
        - breaking_atomic_constraints: Array of breaking atomic constraints
        - lecturer_internal_id: Reference to the lecturer
        - raw_text: The original constraint text from lecturer_constraints
        - Timestamps and metadata
    """
    sql = f"""
        SELECT 
            bc.breaking_id,
            bc.constraints_id,
            bc.breaking_atomic_constraints,
            bc.semester_year,
            bc.semester_number,
            bc.is_seen,
            bc.created_at,
            lc.lecturer_internal_id,
            lc.raw_text,
            lc.structured_rules,
            lc.is_manually_edited,
            lc.original_raw_text
        FROM {TABLE} bc
        JOIN lecturer_constraints lc ON bc.constraints_id = lc.constraints_id
        WHERE lc.schedule_id = $1
        ORDER BY bc.created_at DESC
    """
    
    rows = await fetch_all(sql, schedule_id)
    return [_parse_json_fields(dict(r)) for r in rows]


async def mark_as_seen(breaking_id: int) -> Optional[Dict[str, Any]]:
    """
    Mark a breaking constraint as seen by the secretary.
    
    Args:
        breaking_id: ID of the breaking constraint
    
    Returns:
        Updated breaking constraint record, or None if not found
    """
    sql = f"""
        UPDATE {TABLE}
        SET is_seen = TRUE
        WHERE {ID_COL} = $1
        RETURNING *
    """
    rec = await fetch_one(sql, breaking_id)
    return dict(rec) if rec else None


async def mark_all_as_seen(year: int, number: int) -> int:
    """
    Mark all breaking constraints for a semester as seen.
    
    Args:
        year: Semester year
        number: Semester number
    
    Returns:
        Number of constraints marked as seen
    """
    sql = f"""
        UPDATE {TABLE}
        SET is_seen = TRUE
        WHERE semester_year = $1 AND semester_number = $2 AND is_seen = FALSE
    """
    result = await execute(sql, year, number)
    if result and result.startswith("UPDATE"):
        return int(result.split()[-1])
    return 0


async def get_unseen_count(year: int, number: int) -> int:
    """
    Get count of unseen breaking constraints for a semester.
    
    Args:
        year: Semester year
        number: Semester number
    
    Returns:
        Count of unseen constraints
    """
    sql = f"""
        SELECT COUNT(*) as count
        FROM {TABLE}
        WHERE semester_year = $1 AND semester_number = $2 AND is_seen = FALSE
    """
    rec = await fetch_one(sql, year, number)
    return rec['count'] if rec else 0


async def get_breaking_constraint(breaking_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a single breaking constraint by ID (grouped structure).
    
    Args:
        breaking_id: ID of the breaking constraint
    
    Returns:
        Breaking constraint with grouped atomic constraints, or None if not found.
        Contains breaking_atomic_constraints array with all breaking atomics for this constraint.
        Includes raw_text from lecturer_constraints.
    """
    sql = f"""
        SELECT 
            bc.breaking_id,
            bc.constraints_id,
            bc.breaking_atomic_constraints,
            bc.semester_year,
            bc.semester_number,
            bc.is_seen,
            bc.created_at,
            lc.lecturer_internal_id,
            lc.raw_text,
            lc.structured_rules,
            lc.is_manually_edited,
            lc.original_raw_text
        FROM {TABLE} bc
        JOIN lecturer_constraints lc ON bc.constraints_id = lc.constraints_id
        WHERE bc.{ID_COL} = $1
    """
    rec = await fetch_one(sql, breaking_id)
    return _parse_json_fields(dict(rec)) if rec else None


async def delete_breaking_constraint(breaking_id: int) -> bool:
    """
    Delete a breaking constraint by ID.
    
    Args:
        breaking_id: ID of the breaking constraint
    
    Returns:
        True if deleted, False otherwise
    """
    sql = f"DELETE FROM {TABLE} WHERE {ID_COL} = $1 RETURNING {ID_COL}"
    rec = await fetch_one(sql, breaking_id)
    return bool(rec)


async def delete_by_constraint(constraints_id: int) -> int:
    """Delete all breaking-constraint rows tied to a single lecturer constraint.

    Returns the number of rows deleted.
    """
    sql = f"DELETE FROM {TABLE} WHERE constraints_id = $1"
    result = await execute(sql, constraints_id)
    if result and result.startswith("DELETE"):
        try:
            return int(result.split()[-1])
        except (ValueError, IndexError):
            return 0
    return 0


def _atomic_breaks_session(atomic: Dict[str, Any], session: Dict[str, Any]) -> bool:
    """Return True if the given atomic constraint conflicts with the given session.

    A conflict occurs when:
    - The session's ``day_of_week`` is in ``atomic.days``, AND
    - The session's [start_time, end_time) overlaps the atomic's time window.
    Full-day atomics (``time_slot is None``) conflict on any matching day.
    """
    days = atomic.get("days") or []
    try:
        if int(session.get("day_of_week")) not in {int(d) for d in days}:
            return False
    except (TypeError, ValueError):
        return False

    time_slot = atomic.get("time_slot")
    if time_slot is None:
        return True

    try:
        a_start = int(time_slot.get("start_hour", 0)) * 60 + int(
            time_slot.get("start_minute", 0) or 0
        )
        a_end = int(time_slot.get("end_hour", 0)) * 60 + int(
            time_slot.get("end_minute", 0) or 0
        )
    except (TypeError, ValueError):
        return False

    s_start = session.get("start_time")
    s_end = session.get("end_time")
    if s_start is None or s_end is None:
        return False

    s_start_min = s_start.hour * 60 + s_start.minute
    s_end_min = s_end.hour * 60 + s_end.minute

    # Overlap if start1 < end2 AND start2 < end1
    return a_start < s_end_min and s_start_min < a_end


async def recompute_for_constraint(constraints_id: int) -> int:
    """Recompute the breaking_constraints row for a single constraint.

    Used after a secretary edits the structured rules: the previously stored
    breaking atomics may reference indices/times that no longer exist. This
    helper:

    1. Loads the constraint and its lecturer's scheduled sessions.
    2. Deletes any existing breaking_constraints row for this constraint.
    3. Re-evaluates each atomic against those sessions and, if at least one
       atomic conflicts, inserts a fresh breaking row whose
       ``breaking_atomic_constraints`` array contains the conflicting atomics
       (with their new indices in the post-edit structured_rules).

    Returns the number of breaking-atomic entries inserted (0 when nothing
    breaks). Best-effort: the caller should treat exceptions as non-fatal.
    """
    import json

    from src.repositories import constraints as constraints_repo
    from src.repositories import courses_schedules as sessions_repo

    constraint = await constraints_repo.get_constraint(constraints_id)
    if not constraint:
        return 0

    structured = constraint.get("structured_rules") or {}
    atomics = structured.get("atomic_constraints") or []
    if not isinstance(atomics, list):
        atomics = []

    # Always delete any stale rows for this constraint before re-inserting.
    await delete_by_constraint(constraints_id)

    if not atomics:
        return 0

    lecturer_id = constraint.get("lecturer_internal_id")
    if lecturer_id is None:
        return 0

    sessions = await sessions_repo.list_sessions_for_lecturer(lecturer_id)
    if not sessions:
        return 0

    schedule_id = constraint.get("schedule_id")
    if schedule_id is not None:
        sessions = [s for s in sessions if s.get("schedule_id") == schedule_id]

    # Find conflicting atomics in the new list.
    conflicts: List[Dict[str, Any]] = []
    for idx, atomic in enumerate(atomics):
        if not isinstance(atomic, dict):
            continue
        if any(_atomic_breaks_session(atomic, s) for s in sessions):
            conflicts.append(
                {
                    "atomic_constraint_index": idx,
                    "type": atomic.get("type"),
                    "days": atomic.get("days", []),
                    "time_slot": atomic.get("time_slot"),
                }
            )

    if not conflicts:
        return 0

    sql = f"""
        INSERT INTO {TABLE} (
            constraints_id,
            breaking_atomic_constraints,
            semester_year,
            semester_number,
            is_seen
        ) VALUES ($1, $2, $3, $4, FALSE)
        ON CONFLICT (constraints_id, semester_year, semester_number)
        DO UPDATE SET
            breaking_atomic_constraints = EXCLUDED.breaking_atomic_constraints,
            is_seen = FALSE,
            created_at = CURRENT_TIMESTAMP
        RETURNING breaking_id
    """
    await fetch_one(
        sql,
        constraints_id,
        json.dumps(conflicts),
        constraint.get("semester_year"),
        constraint.get("semester_number"),
    )
    return len(conflicts)


async def list_by_lecturer(
        year: int,
        number: int,
        lecturer_id: int,
) -> List[Dict[str, Any]]:
    """
    Get breaking constraints for a specific lecturer in a specific semester.

    Args:
        year: Semester year
        number: Semester number
        lecturer_id: The internal ID of the lecturer
    
    Returns:
        List of breaking constraints including raw_text from lecturer_constraints
    """
    where_clause = "bc.semester_year = $1 AND bc.semester_number = $2 AND lc.lecturer_internal_id = $3"

    sql = f"""
        SELECT 
            bc.breaking_id,
            bc.constraints_id,
            bc.breaking_atomic_constraints,
            bc.semester_year,
            bc.semester_number,
            bc.is_seen,
            bc.created_at,
            lc.lecturer_internal_id,
            lc.raw_text,
            lc.structured_rules,
            lc.is_manually_edited,
            lc.original_raw_text
        FROM {TABLE} bc
        JOIN lecturer_constraints lc ON bc.constraints_id = lc.constraints_id
        WHERE {where_clause}
        ORDER BY bc.created_at DESC
    """

    rows = await fetch_all(sql, year, number, lecturer_id)
    return [_parse_json_fields(dict(r)) for r in rows]