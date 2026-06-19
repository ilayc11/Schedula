# src/input_convertor/load_constraints.py
"""
Bulk-load lecturer constraints from a CSV file directly into the
`lecturer_constraints` table.

The CSV is expected to have a header row whose names match the table columns.
Any column in the CSV that is not an actual table column (e.g. name columns)
is silently ignored, so the file can carry extra helper columns.

Empty CSV cells become SQL NULL. Boolean columns accept t/f/true/false/1/0.
`structured_rules` is stored as JSONB. The explicit `constraints_id` values
from the CSV are preserved using OVERRIDING SYSTEM VALUE.

Requirements:
  - DB reachable (settings.database_url)
  - Referenced users + semesters already exist (FK constraints)

Usage:
  python -m src.input_convertor.load_constraints
  python -m src.input_convertor.load_constraints --csv path/to/lecturer_constraints.csv
"""

import argparse
import asyncio
import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from src.database.database import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_CSV = Path(__file__).parent / "lecturer_constraints.csv"

# Actual columns of the lecturer_constraints table (constraints_id is an
# identity column but can be set explicitly with OVERRIDING SYSTEM VALUE).
TABLE = "lecturer_constraints"
INT_COLS = {"constraints_id", "lecturer_internal_id", "schedule_id", "semester_year", "semester_number"}
BOOL_COLS = {"secretary_override_as_hard", "is_manually_edited"}
JSON_COLS = {"structured_rules"}
TEXT_COLS = {"raw_text", "original_raw_text"}
TS_COLS = {"last_updated_at"}
TABLE_COLS = INT_COLS | BOOL_COLS | JSON_COLS | TEXT_COLS | TS_COLS


def _parse_bool(value: str) -> Optional[bool]:
    v = value.strip().lower()
    if v in ("t", "true", "1", "yes", "y"):
        return True
    if v in ("f", "false", "0", "no", "n"):
        return False
    return None


def _parse_timestamp(value: str) -> datetime:
    """Parse a CSV timestamp into a timezone-aware datetime.

    Handles Postgres-style offsets like '+00' by normalizing to '+00:00'
    which datetime.fromisoformat understands.
    """
    text = value.strip().replace(" ", "T", 1)
    # Normalize a trailing 2-digit timezone offset (e.g. +00) to +00:00.
    for sign in ("+", "-"):
        idx = text.rfind(sign)
        if idx > 10 and len(text) - idx == 3:  # offset like +00
            text = text + ":00"
            break
    return datetime.fromisoformat(text)


def _coerce(col: str, raw: str) -> Any:
    """Convert a raw CSV string into the right Python type, or None if empty."""
    if raw is None:
        return None
    value = raw.strip()
    if value == "":
        return None
    if col in INT_COLS:
        return int(value)
    if col in BOOL_COLS:
        return _parse_bool(value)
    if col in JSON_COLS:
        # Validate it is JSON, then pass the compact string for JSONB casting.
        return json.dumps(json.loads(value))
    if col in TS_COLS:
        # asyncpg needs a real datetime for timestamptz columns.
        return _parse_timestamp(value)
    # TEXT columns: pass through as string.
    return value


def _row_to_record(row: Dict[str, str]) -> Dict[str, Any]:
    """Keep only real table columns and coerce their values."""
    record: Dict[str, Any] = {}
    for col, raw in row.items():
        if col not in TABLE_COLS:
            continue  # ignore non-table columns (e.g. name columns)
        record[col] = _coerce(col, raw)
    return record


def _build_insert(record: Dict[str, Any]) -> tuple[str, list]:
    cols = list(record.keys())
    placeholders = []
    values = []
    for i, col in enumerate(cols, start=1):
        if col in JSON_COLS:
            placeholders.append(f"${i}::jsonb")
        else:
            placeholders.append(f"${i}")
        values.append(record[col])

    col_sql = ", ".join(cols)
    ph_sql = ", ".join(placeholders)
    # OVERRIDING SYSTEM VALUE lets us insert explicit constraints_id values
    # into the GENERATED ALWAYS AS IDENTITY column.
    override = "OVERRIDING SYSTEM VALUE " if "constraints_id" in record else ""
    sql = f"INSERT INTO {TABLE} ({col_sql}) {override}VALUES ({ph_sql})"
    return sql, values


async def _sync_identity_sequence(conn) -> None:
    """Advance the identity sequence past the max explicit id we inserted."""
    await conn.execute(
        f"""
        SELECT setval(
            pg_get_serial_sequence('{TABLE}', 'constraints_id'),
            COALESCE((SELECT MAX(constraints_id) FROM {TABLE}), 1),
            true
        )
        """
    )


async def main(csv_path: Path) -> None:
    logger.info("=== LOAD CONSTRAINTS ===")
    logger.info(f"CSV file: {csv_path}")

    with csv_path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    if not rows:
        logger.warning("CSV has no data rows. Nothing to do.")
        return

    ignored = [c for c in (rows[0].keys()) if c not in TABLE_COLS]
    if ignored:
        logger.info(f"Ignoring non-table columns: {ignored}")

    inserted = 0
    await db.connect()
    try:
        async with db.transaction() as conn:
            for idx, row in enumerate(rows, start=1):
                record = _row_to_record(row)
                if not record:
                    logger.warning(f"Row {idx}: no usable columns, skipping.")
                    continue
                sql, values = _build_insert(record)
                await conn.execute(sql, *values)
                inserted += 1
                logger.info(
                    f"Row {idx}: inserted constraint "
                    f"id={record.get('constraints_id')} "
                    f"lecturer={record.get('lecturer_internal_id')} "
                    f"semester={record.get('semester_year')}/{record.get('semester_number')}"
                )
            await _sync_identity_sequence(conn)
    finally:
        await db.disconnect()

    logger.info(f"=== DONE: inserted {inserted}/{len(rows)} rows ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bulk-load lecturer constraints from CSV.")
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_CSV,
        help="Path to the lecturer_constraints CSV file.",
    )
    args = parser.parse_args()
    asyncio.run(main(args.csv))
