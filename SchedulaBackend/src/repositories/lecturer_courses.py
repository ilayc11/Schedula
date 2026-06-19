from typing import Dict, List, Optional, Any

from src.repositories.base import execute, fetch_all, fetch_one, update_row_returning, delete_row, upsert_row_returning

TABLE = "lecturer_courses"
ID_COL = "lecturer_course_id"


async def create_lecturer_course_upsert(lecturer_internal_id: int, offering_id: int, role: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Create or update a link between lecturer and course offering."""
    data = {
        "lecturer_internal_id": lecturer_internal_id,
        "offering_id": offering_id,
        "role": role
    }
    return await upsert_row_returning(TABLE, ["lecturer_internal_id", "offering_id"], data)


async def get_by_id(lecturer_course_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a single lecturer-course link by its internal ID."""
    rec = await fetch_one(f"SELECT * FROM {TABLE} WHERE {ID_COL} = $1", lecturer_course_id)
    return dict(rec) if rec else None


async def list_all() -> List[Dict[str, Any]]:
    """Fetch all lecturer-course assignments."""
    rows = await fetch_all(f"SELECT * FROM {TABLE}")
    return [dict(r) for r in rows]


async def list_for_lecturer(lecturer_internal_id: int) -> List[Dict[str, Any]]:
    """Fetch all course offerings assigned to a specific lecturer."""
    rows = await fetch_all(
        f"SELECT * FROM {TABLE} WHERE lecturer_internal_id = $1", lecturer_internal_id
    )
    return [dict(r) for r in rows]


async def list_for_offering(offering_id: int) -> List[Dict[str, Any]]:
    """Fetch all lecturers assigned to a specific course offering."""
    rows = await fetch_all(f"SELECT * FROM {TABLE} WHERE offering_id = $1", offering_id)
    return [dict(r) for r in rows]


async def list_by_role(role: str) -> List[Dict[str, Any]]:
    """Fetch all lecturer-course links with a specific role."""
    rows = await fetch_all(f"SELECT * FROM {TABLE} WHERE role = $1", role)
    return [dict(r) for r in rows]


async def list_for_course_number(course_number: int) -> List[Dict[str, Any]]:
    """Fetch all lecturer-course assignments for a given course number, by joining with course_offering."""
    sql = """
        SELECT lc.*
        FROM lecturer_courses lc
        JOIN course_offering co ON lc.offering_id = co.offering_id
        WHERE co.course_number = $1
    """
    rows = await fetch_all(sql, course_number)
    return [dict(r) for r in rows]


async def get_link(lecturer_internal_id: int, offering_id: int) -> Optional[Dict[str, Any]]:
    """Fetch a single lecturer-course link by lecturer and offering (unique key)."""
    rec = await fetch_one(
        f"SELECT * FROM {TABLE} WHERE lecturer_internal_id = $1 AND offering_id = $2",
        lecturer_internal_id,
        offering_id
    )
    return dict(rec) if rec else None


async def update_lecturer_course(lecturer_course_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update a lecturer-course link and return the updated object."""
    return await update_row_returning(TABLE, ID_COL, lecturer_course_id, updates)


async def delete_lecturer_course(lecturer_course_id: int) -> bool:
    """Delete a lecturer-course link by its internal ID."""
    result = await delete_row(TABLE, ID_COL, lecturer_course_id)
    return result.startswith("DELETE 1")


async def delete_link(lecturer_internal_id: int, offering_id: int) -> bool:
    """Delete a link between a lecturer and a course offering."""
    sql = f"DELETE FROM {TABLE} WHERE lecturer_internal_id = $1 AND offering_id = $2"
    result = await execute(sql, lecturer_internal_id, offering_id)
    return result.startswith("DELETE 1")


async def list_courses_with_details_for_lecturer(lecturer_internal_id: int) -> List[Dict[str, object]]:
    """
    Return all courses assigned to a specific lecturer with course name and number.
    Joins lecturer_courses, course_offering, and courses tables.
    """
    sql = """
        SELECT 
            c.course_number,
            c.course_name,
            co.group_number,
            co.academic_year,
            co.semester,
            lc.role
        FROM lecturer_courses lc
        JOIN course_offering co ON lc.offering_id = co.offering_id
        JOIN courses c ON co.course_number = c.course_number
        WHERE lc.lecturer_internal_id = $1
        ORDER BY c.course_number, co.group_number
    """
    rows = await fetch_all(sql, lecturer_internal_id)
    return [dict(r) for r in rows]


async def list_unique_lecturer_ids_for_semester(semester_year: int, semester_number: int) -> List[int]:
    """Return unique lecturer IDs that teach offerings in a specific semester."""
    sql = """
        SELECT DISTINCT lc.lecturer_internal_id
        FROM lecturer_courses lc
        JOIN course_offering co ON lc.offering_id = co.offering_id
        WHERE co.academic_year = $1 AND co.semester = $2
        ORDER BY lc.lecturer_internal_id
    """
    rows = await fetch_all(sql, semester_year, semester_number)
    return [int(row["lecturer_internal_id"]) for row in rows]
