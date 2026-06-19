import json
from typing import Dict, List, Optional, Any

from src.repositories.base import execute, fetch_one, fetch_all, delete_row, insert_row_returning

TABLE = "fairness_reports"
ID_COL = "report_id"


def _serialize_json_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Serialize dict/list fields to JSON strings for psycopg2.
    
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
    
    # Parse JSONB fields if present
    json_fields = ['fullfilled_constraints_json', 'broken_constraints_json']
    for field in json_fields:
        if field in parsed and isinstance(parsed[field], str):
            try:
                parsed[field] = json.loads(parsed[field])
            except (json.JSONDecodeError, TypeError):
                pass
    
    return parsed


async def create_fairness_report(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Create a new fairness report and return the full object."""
    serialized_data = _serialize_json_fields(data)
    result = await insert_row_returning(TABLE, serialized_data)
    return _parse_json_fields(result) if result else None


async def get_report(report_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a single report by its internal ID."""
    rec = await fetch_one(f"SELECT * FROM {TABLE} WHERE {ID_COL} = $1", report_id)
    return _parse_json_fields(dict(rec)) if rec else None


async def list_reports_for_schedule(schedule_id: int) -> List[Dict[str, Any]]:
    """Fetch all fairness reports for a specific schedule."""
    rows = await fetch_all(f"SELECT * FROM {TABLE} WHERE schedule_id = $1", schedule_id)
    return [_parse_json_fields(dict(r)) for r in rows]


async def delete_report(report_id: int) -> bool:
    """Delete a report by its internal ID."""
    result = await delete_row(TABLE, ID_COL, report_id)
    return result.startswith("DELETE 1")