from typing import Any, Dict, Optional

from src.repositories.base import fetch_one


async def get_status_state(semester_year: int, semester_number: int) -> Optional[Dict[str, Any]]:
    sql = """
        SELECT *
        FROM semester_period_state
        WHERE semester_year = $1 AND semester_number = $2
        LIMIT 1
    """
    row = await fetch_one(sql, semester_year, semester_number)
    return dict(row) if row else None


async def upsert_status_state(semester_year: int, semester_number: int, status: str) -> Optional[Dict[str, Any]]:
    sql = """
        INSERT INTO semester_period_state (
            semester_year,
            semester_number,
            last_seen_status,
            updated_at
        )
        VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
        ON CONFLICT (semester_year, semester_number)
        DO UPDATE SET
            last_seen_status = EXCLUDED.last_seen_status,
            updated_at = CURRENT_TIMESTAMP
        RETURNING *
    """
    row = await fetch_one(sql, semester_year, semester_number, status)
    return dict(row) if row else None
