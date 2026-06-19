import json
from typing import Dict, List, Optional, Any

from src.repositories.base import execute, fetch_one, fetch_all, update_row_returning, delete_row

TABLE = "lecturer_constraints"
ID_COL = "constraints_id"


def _serialize_json_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Serialize dict/list fields to JSON strings for psycopg2.
    
    psycopg2 expects JSONB fields to be JSON strings, not Python objects.
    This function converts any dict or list values to JSON strings.
    
    Args:
        data: Dictionary with potential dict/list values
        
    Returns:
        Dictionary with serialized JSON fields
    """
    serialized = {}
    for key, value in data.items():
        if isinstance(value, (dict, list)):
            serialized[key] = json.dumps(value)
        else:
            serialized[key] = value
    return serialized


def _parse_json_fields(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse JSON string fields from psycopg2 into Python objects.
    
    Args:
        record: Dictionary containing potential JSON string fields
        
    Returns:
        Dictionary with parsed JSON fields
    """
    parsed = record.copy()
    
    # Parse structured_rules if present
    if 'structured_rules' in parsed and isinstance(parsed['structured_rules'], str):
        try:
            parsed['structured_rules'] = json.loads(parsed['structured_rules'])
        except (json.JSONDecodeError, TypeError):
            pass
    
    return parsed


async def create_constraint(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Create a new constraint and return the full object."""
    # Serialize any dict/list fields to JSON strings
    serialized_data = _serialize_json_fields(data)
    
    cols = ", ".join(serialized_data.keys())
    placeholders = ", ".join([f"${i}" for i in range(1, len(serialized_data) + 1)])
    # The last_updated_at column is handled by the database DEFAULT CURRENT_TIMESTAMP,
    # so we don't need to pass it in data.
    sql = f"INSERT INTO {TABLE} ({cols}) VALUES ({placeholders}) RETURNING *"
    rec = await fetch_one(sql, *serialized_data.values())
    return _parse_json_fields(dict(rec)) if rec else None

async def get_constraint(constraints_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a single constraint by its internal ID."""
    rec = await fetch_one(f"SELECT * FROM {TABLE} WHERE {ID_COL} = $1", constraints_id)
    return _parse_json_fields(dict(rec)) if rec else None


async def list_constraints() -> List[Dict[str, Any]]:
    """Fetch all constraints."""
    rows = await fetch_all(f"SELECT * FROM {TABLE} ORDER BY last_updated_at DESC")
    return [_parse_json_fields(dict(r)) for r in rows]


async def list_constraints_by_user(lecturer_internal_id: int) -> List[Dict[str, Any]]:
    """Fetch all constraints for a specific lecturer."""
    rows = await fetch_all(
        f"SELECT * FROM {TABLE} WHERE lecturer_internal_id = $1 ORDER BY last_updated_at DESC",
        lecturer_internal_id
    )
    return [_parse_json_fields(dict(r)) for r in rows]


async def list_constraints_by_schedule(schedule_id: int) -> List[Dict[str, Any]]:
    """Fetch all constraints for a specific schedule."""
    rows = await fetch_all(
        f"SELECT * FROM {TABLE} WHERE schedule_id = $1 ORDER BY last_updated_at DESC",
        schedule_id
    )
    return [_parse_json_fields(dict(r)) for r in rows]


async def list_constraints_by_semester(year: int, number: int) -> List[Dict[str, Any]]:
    """Fetch all constraints for a specific semester (year + semester number)."""
    rows = await fetch_all(
        f"SELECT * FROM {TABLE} WHERE semester_year = $1 AND semester_number = $2 ORDER BY last_updated_at DESC",
        year,
        number
    )
    return [_parse_json_fields(dict(r)) for r in rows]


async def get_latest_constraint_by_lecturer(lecturer_internal_id: int) -> Optional[Dict[str, Any]]:
    """Fetch the most recently updated constraint for a specific lecturer."""
    rec = await fetch_one(
        f"SELECT * FROM {TABLE} WHERE lecturer_internal_id = $1 ORDER BY last_updated_at DESC LIMIT 1",
        lecturer_internal_id
    )
    return _parse_json_fields(dict(rec)) if rec else None


async def update_constraint(constraints_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update a constraint and return the updated object."""
    # Serialize any dict/list fields to JSON strings
    serialized_updates = _serialize_json_fields(updates)
    rec = await update_row_returning(TABLE, ID_COL, constraints_id, serialized_updates)
    return _parse_json_fields(rec) if rec else None


async def mark_as_manually_edited(
    constraints_id: int,
    original_raw_text: Optional[str],
    new_structured_rules: Dict[str, Any],
    new_raw_text: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Apply a secretary-authored edit to a constraint in a single UPDATE.

    Sets is_manually_edited=TRUE, preserves original_raw_text (only when it
    was previously NULL — once set, the very first lecturer text wins so we
    never lose it across multiple edits), and replaces structured_rules and
    raw_text with the secretary's values.
    """
    sql = f"""
        UPDATE {TABLE}
        SET
            structured_rules = $1,
            raw_text = $2,
            is_manually_edited = TRUE,
            original_raw_text = COALESCE(original_raw_text, $3),
            last_updated_at = CURRENT_TIMESTAMP
        WHERE {ID_COL} = $4
        RETURNING *
    """
    rec = await fetch_one(
        sql,
        json.dumps(new_structured_rules) if new_structured_rules is not None else None,
        new_raw_text,
        original_raw_text,
        constraints_id,
    )
    return _parse_json_fields(dict(rec)) if rec else None


async def delete_constraint(constraints_id: int) -> bool:
    """Delete a constraint by its internal ID."""
    result = await delete_row(TABLE, ID_COL, constraints_id)
    return result.startswith("DELETE 1")


async def list_constraints_by_semester_and_lecturer(
    year: int,
    number: int,
    lecturer_id: int
) -> List[Dict[str, Any]]:
    """Fetch all constraints for a specific lecturer in a specific semester."""
    sql = f"""
        SELECT * FROM {TABLE} 
        WHERE semester_year = $1 AND semester_number = $2 AND lecturer_internal_id = $3
        ORDER BY last_updated_at DESC
    """
    rows = await fetch_all(sql, year, number, lecturer_id)
    return [_parse_json_fields(dict(r)) for r in rows]