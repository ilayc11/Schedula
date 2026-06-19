from typing import Dict, List, Optional, Any
from src.repositories.base import fetch_all


async def get_detailed_schedule(
        schedule_id: Optional[int] = None,
        lecturer_internal_id: Optional[int] = None,
        semester_year: Optional[int] = None,
        semester_number: Optional[int] = None,
        day_of_week: Optional[int] = None,
        lecturer_name_filter: Optional[str] = None,  # Filter by lecturer name (partial/full)
        group_number_filter: Optional[int] = None,  # Filter by group number
        target_department_id: Optional[int] = None,  # Cohort filter: department
        target_year_level: Optional[int] = None,  # Cohort filter: year level
) -> List[Dict[str, object]]:
    """
    Fetches the detailed schedule by joining necessary tables,
    allowing filtering by schedule ID, lecturer ID, semester, day, lecturer name, group number, and cohort.
    
    Note: Returns sessions with cohort information aggregated. If filtering by cohort,
    only sessions for offerings targeting that cohort will be returned.
    """

    # Base SQL Query with cohort join
    sql = """
    SELECT
        CS.session_id, CS.day_of_week, CS.start_time, CS.end_time,
        CS.offering_id, CS.lecturer_internal_id, CS.schedule_id,
        S.semester_year, S.semester_number, 

        (U.first_name || ' ' || U.last_name) AS lecturer_name, 
        C.course_name,
        C.course_number, 
        CO.group_number,
        
        -- Aggregate cohorts as JSON array
        COALESCE(
            json_agg(
                json_build_object(
                    'target_department_id', OC.target_department_id,
                    'target_year_level', OC.target_year_level
                )
            ) FILTER (WHERE OC.cohort_id IS NOT NULL),
            '[]'
        ) AS cohorts

    FROM courses_schedules AS CS
    JOIN schedules AS S ON CS.schedule_id = S.schedule_id
    JOIN users AS U ON CS.lecturer_internal_id = U.user_internal_id
    JOIN course_offering AS CO ON CS.offering_id = CO.offering_id
    JOIN courses AS C ON CO.course_number = C.course_number
    LEFT JOIN offering_cohorts AS OC ON CO.offering_id = OC.offering_id
    """

    # Dynamic WHERE Clause Construction
    conditions = []
    params = []
    param_count = 1

    # Define filtering
    if schedule_id is not None:
        conditions.append(f"CS.schedule_id = ${param_count}")
        params.append(schedule_id)
        param_count += 1

    if lecturer_internal_id is not None:
        conditions.append(f"CS.lecturer_internal_id = ${param_count}")
        params.append(lecturer_internal_id)
        param_count += 1

    if semester_year is not None and semester_number is not None:
        conditions.append(f"S.semester_year = ${param_count} AND S.semester_number = ${param_count + 1}")
        params.extend([semester_year, semester_number])
        param_count += 2

    if day_of_week is not None:
        conditions.append(f"CS.day_of_week = ${param_count}")
        params.append(day_of_week)
        param_count += 1

    if lecturer_name_filter is not None:
        conditions.append(f"(U.first_name || ' ' || U.last_name) ILIKE ${param_count}")
        params.append(f"%{lecturer_name_filter}%")
        param_count += 1

    if group_number_filter is not None:
        conditions.append(f"CO.group_number = ${param_count}")
        params.append(group_number_filter)
        param_count += 1

    # Cohort filters need to be in the WHERE clause for the join
    if target_department_id is not None:
        conditions.append(f"OC.target_department_id = ${param_count}")
        params.append(target_department_id)
        param_count += 1

    if target_year_level is not None:
        conditions.append(f"OC.target_year_level = ${param_count}")
        params.append(target_year_level)
        param_count += 1

    # Append WHERE clause if conditions exist
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)

    # Group by all non-aggregated columns
    sql += """
    GROUP BY 
        CS.session_id, CS.day_of_week, CS.start_time, CS.end_time,
        CS.offering_id, CS.lecturer_internal_id, CS.schedule_id,
        S.semester_year, S.semester_number,
        U.first_name, U.last_name,
        C.course_name, C.course_number,
        CO.group_number
    """

    # Ordering Logic
    sql += " ORDER BY CS.schedule_id DESC, CS.day_of_week ASC, CS.start_time ASC"

    rows = await fetch_all(sql, *params)
    return [dict(r) for r in rows]


async def list_offerings_with_details(
        semester_year: int,
        semester_number: int,
        department_id: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Fetches all course offerings for a specific semester with full details:
    Course info, Lecturer info, and Cohorts.
    This serves as the master list for manual scheduling.
    """

    sql = """
    SELECT 
        CO.offering_id, CO.course_number, CO.group_number,
        CO.academic_year, CO.semester, C.course_name, C.credit_points,
        C.degree_level, C.department_id AS course_owner_dept,

        -- Lecturer Info
        LC.lecturer_internal_id,
        (U.first_name || ' ' || U.last_name) AS lecturer_name,
        U.email AS lecturer_email,

        -- Aggregate cohorts as JSON array
        COALESCE(
            json_agg(
                DISTINCT json_build_object(
                    'target_department_id', OC.target_department_id,
                    'target_year_level', OC.target_year_level
                )
            ) FILTER (WHERE OC.cohort_id IS NOT NULL),
            '[]'
        ) AS cohorts

    FROM course_offering AS CO
    JOIN courses AS C ON CO.course_number = C.course_number
    LEFT JOIN lecturer_courses AS LC ON CO.offering_id = LC.offering_id
    LEFT JOIN users AS U ON LC.lecturer_internal_id = U.user_internal_id
    LEFT JOIN offering_cohorts AS OC ON CO.offering_id = OC.offering_id

    WHERE CO.academic_year = $1 AND CO.semester = $2
    """

    params = [semester_year, semester_number]

    if department_id is not None:
        sql += " AND C.department_id = $3"
        params.append(department_id)

    sql += """
    GROUP BY 
        CO.offering_id, CO.course_number, CO.group_number, CO.academic_year, CO.semester,
        C.course_name, C.credit_points, C.degree_level, C.department_id,
        LC.lecturer_internal_id, U.first_name, U.last_name, U.email
    ORDER BY C.course_name ASC, CO.group_number ASC
    """

    rows = await fetch_all(sql, *params)
    return [dict(r) for r in rows]