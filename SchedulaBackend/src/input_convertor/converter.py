# src/input_convertor/converter.py
"""Main data converter orchestrator."""

import logging
from typing import Dict, Any
from .excel_reader import read_lecturers_excel, read_courses_excel
from .mapper import map_lecturers, map_users_from_dedu, map_courses, group_cohorts_by_course
from .api_client import DataLoaderClient
from src.repositories import semesters as semester_repo

logger = logging.getLogger(__name__)


async def load_static_data(
    lecturers_dedu_bytes: bytes,
    courses_bytes: bytes,
) -> Dict[str, Any]:
    """
    Load static, semester-independent data: users (lecturers) and courses.

    Expects the slim deduplicated lecturer file (lecturers_dedu) which contains
    only user identity columns (no course/semester data).
    Safe to run once per academic year or whenever the lecturer/course
    catalogue changes. Run this before load_assignments.

    Returns:
        Summary dict with users_loaded and courses_loaded counts.
    """
    try:
        lecturers_dedu_df = await read_lecturers_excel(lecturers_dedu_bytes)
        courses_df        = await read_courses_excel(courses_bytes)

        users    = map_users_from_dedu(lecturers_dedu_df)
        courses, _ = map_courses(courses_df)  # cohorts ignored here

        async with DataLoaderClient() as client:
            user_id_to_internal = await client.create_users(users)
            courses_count       = await client.create_courses(courses)

        return {
            "status":         "success",
            "users_loaded":   len(user_id_to_internal),
            "courses_loaded": courses_count,
        }
    except Exception as e:
        logger.error(f"load_static_data failed: {e}", exc_info=True)
        raise


async def load_assignments(
    lecturers_bytes: bytes,
    courses_bytes: bytes,
) -> Dict[str, Any]:
    """
    Load semester-specific assignment data: course offerings (with cohorts)
    and lecturer-course links.

    Requires load_static_data to have been run first so that users and
    courses already exist in the DB. User FKs are resolved by DB lookup
    rather than re-insertion.

    Returns:
        Summary dict with offerings_loaded and lecturer_courses_loaded counts.
    """
    try:
        lecturers_df = await read_lecturers_excel(lecturers_bytes)
        courses_df   = await read_courses_excel(courses_bytes)

        _, offerings, lecturer_courses = map_lecturers(lecturers_df)  # users ignored here
        _, cohorts                     = map_courses(courses_df)       # courses ignored here

        if offerings:
            first_offering = offerings[0]
            semester_year = int(first_offering["academic_year"])
            semester_num = int(first_offering["semester"])
            result = await semester_repo.get_semester(semester_year, semester_num)
            if not result:
                logger.warning(f"Validation failed: Semester {semester_year}/{semester_num} not found in DB.")
                return {"status": "failure", "detail": f"Semester {semester_year}/{semester_num} not found in DB. Please create it first."}

        cohorts_by_course      = group_cohorts_by_course(cohorts)
        offerings_with_cohorts = [
            {**o, "cohorts": cohorts_by_course.get(int(o["course_number"]), [])}
            for o in offerings
        ]

        # Collect unique uids to resolve FKs from existing DB rows
        uids = list({str(lc["user_id"]) for lc in lecturer_courses})

        async with DataLoaderClient() as client:
            # Resolve user FKs from DB (users already exist from load_static_data)
            user_id_to_internal = await client.resolve_users_from_db(uids)

            # Create offerings + cohorts atomically
            offering_key_to_id = await client.create_offerings(offerings_with_cohorts)

            # Create lecturer-course links
            lc_count = await client.create_lecturer_courses(
                lecturer_courses, user_id_to_internal, offering_key_to_id
            )

        return {
            "status":                  "success",
            "offerings_loaded":        len(offering_key_to_id),
            "lecturer_courses_loaded": lc_count,
        }
    except Exception as e:
        logger.error(f"load_assignments failed: {e}", exc_info=True)
        raise


async def convert_and_load(
    lecturers_dedu_bytes: bytes,
    lecturers_bytes: bytes,
    courses_bytes: bytes,
) -> Dict[str, Any]:
    """
    Convenience wrapper: runs load_static_data then load_assignments in sequence.
    Used by run_wet.py for a single full-pipeline execution.

    lecturers_dedu_bytes — slim deduplicated file for user population.
    lecturers_bytes      — full lecturer file for offering/assignment data.
    """
    try:
        static  = await load_static_data(lecturers_dedu_bytes, courses_bytes)
        assigns = await load_assignments(lecturers_bytes, courses_bytes)
        return {
            "status":                  "success",
            "users_loaded":            static["users_loaded"],
            "courses_loaded":          static["courses_loaded"],
            "offerings_loaded":        assigns["offerings_loaded"],
            "lecturer_courses_loaded": assigns["lecturer_courses_loaded"],
        }
    except Exception as e:
        logger.error(f"convert_and_load failed: {e}", exc_info=True)
        raise
