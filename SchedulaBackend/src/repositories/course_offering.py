from typing import Dict, List, Optional, Any

from src.repositories.base import execute, fetch_one, fetch_all, update_row_returning, delete_row

TABLE = "course_offering"
COHORTS_TABLE = "offering_cohorts"
ID_COL = "offering_id"


async def create_course_offering(data: Dict[str, Any], cohorts: Optional[List[Dict[str, Any]]] = None) -> int:
    """
    Insert a new course offering into the database.
    Returns the offering_id.
    """
    cols = ", ".join(data.keys())
    placeholders = ", ".join([f"${i}" for i in range(1, len(data) + 1)])
    sql = f"INSERT INTO {TABLE} ({cols}) VALUES ({placeholders}) RETURNING offering_id"
    
    result = await fetch_one(sql, *data.values())
    offering_id = result['offering_id']
    
    # Insert cohorts if provided
    if cohorts:
        await add_offering_cohorts(offering_id, cohorts)
    
    return offering_id


async def add_offering_cohorts(offering_id: int, cohorts: List[Dict[str, Any]]) -> str:
    """
    Add cohorts to an offering.
    Both target_department_id and target_year_level are REQUIRED (NOT NULL).
    """
    if not cohorts:
        return "No cohorts to add"
    
    # Build insert query for multiple cohorts
    values = []
    for cohort in cohorts:
        target_dept = cohort.get('target_department_id')
        target_year = cohort.get('target_year_level')
        
        # Validate required fields (NOT NULL constraint)
        if target_dept is None or target_year is None:
            raise ValueError(f"Both target_department_id and target_year_level are required for cohort. Got dept={target_dept}, year={target_year}")
        
        values.append(f"({offering_id}, {target_dept}, {target_year})")
    
    sql = f"""
        INSERT INTO {COHORTS_TABLE} (offering_id, target_department_id, target_year_level)
        VALUES {', '.join(values)}
        ON CONFLICT (offering_id, target_department_id, target_year_level) DO NOTHING
    """
    return await execute(sql)


async def get_course_offering(offering_id: int) -> Optional[Dict[str, Any]]:
    """
    Return a single course offering by its internal ID, including its cohorts.
    """
    rec = await fetch_one(f"SELECT * FROM {TABLE} WHERE {ID_COL} = $1", offering_id)
    if not rec:
        return None
    
    offering = dict(rec)
    
    # Fetch cohorts
    cohorts = await fetch_all(
        f"SELECT cohort_id, target_department_id, target_year_level FROM {COHORTS_TABLE} WHERE offering_id = $1",
        offering_id
    )
    offering['cohorts'] = [dict(c) for c in cohorts]
    
    return offering


async def list_course_offerings() -> List[Dict[str, Any]]:
    """
    Return all course offerings with their cohorts.
    """
    rows = await fetch_all(f"SELECT * FROM {TABLE}")
    offerings = []
    
    for row in rows:
        offering = dict(row)
        offering_id = offering['offering_id']
        
        # Fetch cohorts for this offering
        cohorts = await fetch_all(
            f"SELECT cohort_id, target_department_id, target_year_level FROM {COHORTS_TABLE} WHERE offering_id = $1",
            offering_id
        )
        offering['cohorts'] = [dict(c) for c in cohorts]
        offerings.append(offering)
    
    return offerings


async def list_course_offerings_by_course(course_number: int) -> List[Dict[str, Any]]:
    """
    Return all offerings for a given course number with their cohorts.
    """
    rows = await fetch_all(f"SELECT * FROM {TABLE} WHERE course_number = $1", course_number)
    offerings = []
    
    for row in rows:
        offering = dict(row)
        offering_id = offering['offering_id']
        
        cohorts = await fetch_all(
            f"SELECT cohort_id, target_department_id, target_year_level FROM {COHORTS_TABLE} WHERE offering_id = $1",
            offering_id
        )
        offering['cohorts'] = [dict(c) for c in cohorts]
        offerings.append(offering)
    
    return offerings


async def list_course_offerings_by_year(academic_year: int) -> List[Dict[str, object]]:
    """
    Return all offerings for a given academic year with their cohorts.
    """
    rows = await fetch_all(f"SELECT * FROM {TABLE} WHERE academic_year = $1", academic_year)
    offerings = []
    
    for row in rows:
        offering = dict(row)
        offering_id = offering['offering_id']
        
        cohorts = await fetch_all(
            f"SELECT cohort_id, target_department_id, target_year_level FROM {COHORTS_TABLE} WHERE offering_id = $1",
            offering_id
        )
        offering['cohorts'] = [dict(c) for c in cohorts]
        offerings.append(offering)
    
    return offerings


async def list_course_offerings_by_semester(academic_year: int, semester: int) -> List[Dict[str, Any]]:
    """
    Return all offerings for a given semester in a specific year with their cohorts.
    """
    rows = await fetch_all(
        f"SELECT * FROM {TABLE} WHERE academic_year = $1 AND semester = $2",
        academic_year,
        semester,
    )
    offerings = []
    
    for row in rows:
        offering = dict(row)
        offering_id = offering['offering_id']
        
        cohorts = await fetch_all(
            f"SELECT cohort_id, target_department_id, target_year_level FROM {COHORTS_TABLE} WHERE offering_id = $1",
            offering_id
        )
        offering['cohorts'] = [dict(c) for c in cohorts]
        offerings.append(offering)
    
    return offerings


async def list_course_offerings_by_cohort(
    department_id: int,
    year_level: int,
    academic_year: int,
    semester: int
) -> List[Dict[str, object]]:
    """
    Return all offerings for a specific cohort in a semester.
    """
    sql = f"""
        SELECT co.* FROM {TABLE} co
        JOIN {COHORTS_TABLE} oc ON co.offering_id = oc.offering_id
        WHERE oc.target_department_id = $1 
        AND oc.target_year_level = $2 
        AND co.academic_year = $3 
        AND co.semester = $4
    """
    rows = await fetch_all(sql, department_id, year_level, academic_year, semester)
    offerings = []
    
    for row in rows:
        offering = dict(row)
        offering_id = offering['offering_id']
        
        cohorts = await fetch_all(
            f"SELECT cohort_id, target_department_id, target_year_level FROM {COHORTS_TABLE} WHERE offering_id = $1",
            offering_id
        )
        offering['cohorts'] = [dict(c) for c in cohorts]
        offerings.append(offering)
    
    return offerings


async def list_course_offerings_by_group(course_number: int, academic_year: int, semester: int, group_number: int) -> Optional[Dict[str, object]]:
    """
    Return a single offering for a specific course, year, semester, and group number with its cohorts.
    """
    rec = await fetch_one(
        f"SELECT * FROM {TABLE} WHERE course_number = $1 AND academic_year = $2 AND semester = $3 AND group_number = $4",
        course_number,
        academic_year,
        semester,
        group_number,
    )
    if not rec:
        return None
    
    offering = dict(rec)
    offering_id = offering['offering_id']
    
    cohorts = await fetch_all(
        f"SELECT cohort_id, target_department_id, target_year_level FROM {COHORTS_TABLE} WHERE offering_id = $1",
        offering_id
    )
    offering['cohorts'] = [dict(c) for c in cohorts]
    
    return offering


async def update_course_offering(offering_id: int, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Update a course offering and return the updated object."""
    return await update_row_returning(TABLE, ID_COL, offering_id, updates)


async def delete_course_offering(offering_id: int) -> bool:
    """Delete a course offering by internal ID (cohorts will cascade delete)."""
    result = await delete_row(TABLE, ID_COL, offering_id)
    return result.startswith("DELETE 1")


async def delete_offering_cohorts(offering_id: int) -> bool:
    """Delete all cohorts for an offering."""
    result = await execute(f"DELETE FROM {COHORTS_TABLE} WHERE offering_id = $1", offering_id)
    return not result.startswith("DELETE 0")
