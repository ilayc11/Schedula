from typing import Dict, List, Optional, Any

from src.repositories.base import execute, fetch_one, fetch_all, update_row_returning, delete_row, insert_row_returning

TABLE = "courses"
ID_COL = "course_id"


async def create_course(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Create a new course and return the full object."""
    return await insert_row_returning(TABLE, data)


async def get_course(course_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a single course by its internal ID."""
    rec = await fetch_one(f"SELECT * FROM {TABLE} WHERE {ID_COL} = $1", course_id)
    return dict(rec) if rec else None


async def list_courses() -> List[Dict[str, Any]]:
    """Fetch all courses."""
    rows = await fetch_all(f"SELECT * FROM {TABLE}")
    return [dict(r) for r in rows]


async def list_courses_by_name(course_name: str) -> List[Dict[str, Any]]:
    """Fetch all courses with the given name (exact match)."""
    rows = await fetch_all(f"SELECT * FROM {TABLE} WHERE course_name = $1", course_name)
    return [dict(r) for r in rows]


async def list_courses_by_number(course_number: int) -> Optional[Dict[str, Any]]:
    """Fetch a single course by its course number (unique)."""
    rec = await fetch_one(f"SELECT * FROM {TABLE} WHERE course_number = $1", course_number)
    return dict(rec) if rec else None


async def list_courses_by_department(department: str) -> List[Dict[str, Any]]:
    """Fetch all courses in a specific department."""
    rows = await fetch_all(f"SELECT * FROM {TABLE} WHERE department = $1", department)
    return [dict(r) for r in rows]


async def list_courses_by_degree(degree_level: int) -> List[Dict[str, Any]]:
    """Fetch all courses for a specific degree level."""
    rows = await fetch_all(f"SELECT * FROM {TABLE} WHERE degree_level = $1", degree_level)
    return [dict(r) for r in rows]


async def list_courses_by_credits(credit: float) -> List[Dict[str, Any]]:
    """Fetch all courses for a specific credit points."""
    rows = await fetch_all(f"SELECT * FROM {TABLE} WHERE credit_points = $1", credit)
    return [dict(r) for r in rows]


async def update_course(course_id: Any, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update a course and return the updated object."""
    return await update_row_returning(TABLE, ID_COL, course_id, updates)


async def delete_course(course_id: Any) -> bool:
    """Delete a course by its internal ID."""
    result = await delete_row(TABLE, ID_COL, course_id)
    return result.startswith("DELETE 1")
