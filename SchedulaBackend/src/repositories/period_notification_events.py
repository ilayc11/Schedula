import json
from datetime import date
from typing import Any, Dict, Optional

from src.repositories.base import fetch_one

TABLE = "period_notification_events"


async def reserve_event(
    semester_year: int,
    semester_number: int,
    event_key: str,
    event_date: date,
    payload: Dict[str, Any],
    source: str,
) -> Optional[Dict[str, Any]]:
    """Create an idempotency row for the event or return the existing one."""
    insert_sql = """
        INSERT INTO period_notification_events (
            semester_year,
            semester_number,
            event_key,
            event_date,
            payload,
            source,
            created_at
        )
        VALUES ($1, $2, $3, $4, $5::jsonb, $6, CURRENT_TIMESTAMP)
        ON CONFLICT (semester_year, semester_number, event_key, event_date)
        DO NOTHING
        RETURNING *
    """
    inserted = await fetch_one(
        insert_sql,
        semester_year,
        semester_number,
        event_key,
        event_date,
        json.dumps(payload),
        source,
    )
    if inserted:
        return dict(inserted)

    existing_sql = """
        SELECT *
        FROM period_notification_events
        WHERE semester_year = $1
          AND semester_number = $2
          AND event_key = $3
          AND event_date = $4
        LIMIT 1
    """
    existing = await fetch_one(existing_sql, semester_year, semester_number, event_key, event_date)
    return dict(existing) if existing else None


async def mark_published(event_id: int) -> Optional[Dict[str, Any]]:
    sql = """
        UPDATE period_notification_events
        SET published_at = CURRENT_TIMESTAMP
        WHERE event_id = $1
        RETURNING *
    """
    row = await fetch_one(sql, int(event_id))
    return dict(row) if row else None
