# src/input_convertor/load_unavailable_user.py
"""
Create a single "always unavailable" lecturer and a matching constraint.

This is a duplicate of ``load_constraints.py`` adapted for one specific job:
instead of bulk-loading a CSV, it provisions a brand-new user whose
constraint is literally "cant work at all" and whose ``structured_rules``
block every day for every working hour.

Day codes follow the project convention: 1=Sunday ... 6=Friday.
Working hours: Sunday-Thursday 08:00-20:00, Friday 08:00-15:00. The blocking
rules below cover that full schedulable window so nothing can be assigned.

The new user + constraint are inserted in a single transaction. FK
constraints require the referenced semester to already exist; the user is
created here so its FK is satisfied. The script is idempotent on ``user_id``:
if a user with the same external id already exists it is reused instead of
inserting a duplicate.

Requirements:
  - DB reachable (settings.database_url)
  - Referenced semester already exists (FK constraint)

Usage:
  python -m src.input_convertor.load_unavailable_user
  python -m src.input_convertor.load_unavailable_user --user-id 999999999 \
      --user-name no_work --email no.work@example.com \
      --semester-year 2027 --semester-number 1
"""

import argparse
import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.database.database import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# --- Defaults for the new "cant work at all" lecturer ---------------------
DEFAULT_USER_ID = "999999999"          # external id, exactly 9 chars
DEFAULT_USER_NAME = "no_work_lecturer"
DEFAULT_FIRST_NAME = "No"
DEFAULT_LAST_NAME = "Work"
DEFAULT_EMAIL = "no.work@example.com"
DEFAULT_ROLE = "L"                     # lecturer
DEFAULT_SEMESTER_YEAR = 2027
DEFAULT_SEMESTER_NUMBER = 1

RAW_TEXT = "cant work at all"

USERS_TABLE = "users"
CONSTRAINTS_TABLE = "lecturer_constraints"

# Per-day full-day working windows (1=Sun ... 6=Fri).
# Sun-Thu run 08:00-20:00, Fri runs 08:00-15:00.
_FULL_DAY_WINDOWS: Dict[int, tuple[int, int]] = {
    1: (8, 20),
    2: (8, 20),
    3: (8, 20),
    4: (8, 20),
    5: (8, 20),
    6: (8, 15),
}


def build_block_everything_rules() -> Dict[str, Any]:
    """Build structured_rules that hard-block every day for all working hours."""
    atomic_constraints: List[Dict[str, Any]] = []
    for day in sorted(_FULL_DAY_WINDOWS):
        start_hour, end_hour = _FULL_DAY_WINDOWS[day]
        atomic_constraints.append(
            {
                "days": [day],
                "type": "block",
                "priority": "hard",
                "time_slot": {
                    "start_hour": start_hour,
                    "start_minute": 0,
                    "end_hour": end_hour,
                    "end_minute": 0,
                },
            }
        )
    return {"atomic_constraints": atomic_constraints}


async def _resolve_department_id(conn, requested: Optional[int]) -> int:
    """Pick a valid department_id, falling back to an existing one."""
    if requested is not None:
        return requested
    row = await conn.fetchrow(
        f"SELECT department_id FROM {USERS_TABLE} ORDER BY user_internal_id LIMIT 1"
    )
    if row and row["department_id"] is not None:
        return int(row["department_id"])
    return 1


async def _get_or_create_user(conn, args: argparse.Namespace) -> int:
    """Return the user_internal_id, creating the lecturer if needed."""
    existing = await conn.fetchrow(
        f"SELECT user_internal_id FROM {USERS_TABLE} WHERE user_id = $1",
        args.user_id,
    )
    if existing:
        user_internal_id = int(existing["user_internal_id"])
        logger.info(f"User already exists (user_id={args.user_id}); reusing internal id {user_internal_id}.")
        return user_internal_id

    department_id = await _resolve_department_id(conn, args.department_id)
    row = await conn.fetchrow(
        f"""
        INSERT INTO {USERS_TABLE}
            (user_id, user_name, first_name, last_name, email, role, department_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING user_internal_id
        """,
        args.user_id,
        args.user_name,
        args.first_name,
        args.last_name,
        args.email,
        args.role,
        department_id,
    )
    user_internal_id = int(row["user_internal_id"])
    logger.info(
        f"Created lecturer user_internal_id={user_internal_id} "
        f"(user_id={args.user_id}, user_name={args.user_name}, department_id={department_id})."
    )
    return user_internal_id


async def _insert_constraint(conn, user_internal_id: int, args: argparse.Namespace) -> int:
    """Insert the fully-blocking constraint for the user; return constraints_id."""
    rules = build_block_everything_rules()
    row = await conn.fetchrow(
        f"""
        INSERT INTO {CONSTRAINTS_TABLE}
            (lecturer_internal_id, semester_year, semester_number,
             raw_text, structured_rules,
             secretary_override_as_hard, is_manually_edited, last_updated_at)
        VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8)
        RETURNING constraints_id
        """,
        user_internal_id,
        args.semester_year,
        args.semester_number,
        RAW_TEXT,
        json.dumps(rules),
        False,
        False,
        datetime.now(timezone.utc),
    )
    constraints_id = int(row["constraints_id"])
    logger.info(
        f"Inserted constraint id={constraints_id} for lecturer={user_internal_id} "
        f"semester={args.semester_year}/{args.semester_number} "
        f"({len(rules['atomic_constraints'])} hard block rules)."
    )
    return constraints_id


async def main(args: argparse.Namespace) -> None:
    logger.info("=== LOAD UNAVAILABLE USER ===")
    logger.info(f"raw_text: {RAW_TEXT!r}")

    await db.connect()
    try:
        async with db.transaction() as conn:
            user_internal_id = await _get_or_create_user(conn, args)
            await _insert_constraint(conn, user_internal_id, args)
    finally:
        await db.disconnect()

    logger.info("=== DONE ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Create an "always unavailable" lecturer and a fully-blocking constraint.'
    )
    parser.add_argument("--user-id", default=DEFAULT_USER_ID, help="External user id (9 chars).")
    parser.add_argument("--user-name", default=DEFAULT_USER_NAME, help="Unique username.")
    parser.add_argument("--first-name", default=DEFAULT_FIRST_NAME)
    parser.add_argument("--last-name", default=DEFAULT_LAST_NAME)
    parser.add_argument("--email", default=DEFAULT_EMAIL)
    parser.add_argument("--role", default=DEFAULT_ROLE, choices=["L", "S"])
    parser.add_argument(
        "--department-id",
        type=int,
        default=None,
        help="Department id. Defaults to an existing department if omitted.",
    )
    parser.add_argument("--semester-year", type=int, default=DEFAULT_SEMESTER_YEAR)
    parser.add_argument("--semester-number", type=int, default=DEFAULT_SEMESTER_NUMBER)
    parsed = parser.parse_args()
    asyncio.run(main(parsed))
