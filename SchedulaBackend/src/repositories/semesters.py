from typing import Dict, List, Optional, Any

from src.repositories.base import execute, fetch_one, fetch_all, update_row_composite_key, update_row_returning

TABLE = "semesters"


async def create_semester(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Create a new semester and return the full created object."""
    cols = ", ".join(data.keys())
    placeholders = ", ".join([f"${i}" for i in range(1, len(data) + 1)])
    sql = f"INSERT INTO {TABLE} ({cols}) VALUES ({placeholders}) RETURNING *"
    rec = await fetch_one(sql, *data.values())
    return dict(rec) if rec else None


async def get_semester(year: int, number: int) -> Optional[Dict[str, Any]]:
    """Fetch a semester by composite key (year, number)."""
    rec = await fetch_one(
        f"SELECT * FROM {TABLE} WHERE semester_year = $1 AND semester_number = $2",
        year,
        number,
    )
    return dict(rec) if rec else None


async def update_semester_status(year: int, number: int, status: str) -> str:
    """Update only the status field of a semester."""
    sql = f"UPDATE {TABLE} SET status = $1 WHERE semester_year = $2 AND semester_number = $3"
    return await execute(sql, status, year, number)


async def list_semesters() -> List[Dict[str, Any]]:
    """Fetch all semesters."""
    rows = await fetch_all(f"SELECT * FROM {TABLE} ORDER BY semester_year DESC, semester_number DESC")
    return [dict(r) for r in rows]


async def update_semester(year: int, number: int, updates: Dict[str, Any]) -> str:
    """Update a semester using its composite primary key (year, number)."""
    key_conditions = {"semester_year": year, "semester_number": number}
    return await update_row_composite_key(TABLE, key_conditions, updates)


async def update_and_get_semester(year: int, number: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update a semester record and return the updated object."""
    update_result = await update_semester(year, number, updates)
    if update_result == "UPDATE 0":
        return None
    return await get_semester(year, number)


async def get_current_semester() -> Optional[Dict[str, Any]]:
    """
    Get the current active semester based on date and status.
    Returns the semester where status is active (SET, SUB, REV, CHA) or
    today's date falls within constraint_start_date to semester_end_date.
    """
    sql = """
        SELECT * FROM semesters 
        WHERE status IN ('SET', 'SUB', 'REV', 'CHA', 'PUB')
           OR (CURRENT_DATE BETWEEN constraint_start_date AND semester_end_date)
        ORDER BY semester_year DESC, semester_number DESC
        LIMIT 1
    """
    rec = await fetch_one(sql)
    return dict(rec) if rec else None