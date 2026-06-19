# src/input_convertor/api_client.py
"""Database loader — writes data directly via repository functions."""

import logging
from typing import Any, Dict, List, Tuple

import src.repositories.users as users_repo
import src.repositories.courses as courses_repo
import src.repositories.course_offering as offering_repo
import src.repositories.lecturer_courses as lc_repo

logger = logging.getLogger(__name__)


class DataLoaderClient:
    """Loads data directly into the database via repository functions.

    The historical name (and `api_client` module path) is retained so callers
    don't have to change. The class no longer makes HTTP calls; it writes
    through the repository layer.
    """

    async def __aenter__(self) -> "DataLoaderClient":
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        pass

    async def create_users(self, users: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Create users via the users repository.

        Returns:
            Mapping of user_id (str) -> user_internal_id (int),
            needed to resolve lecturer_courses FKs later.
        """
        user_id_to_internal: Dict[str, int] = {}
        for user in users:
            try:
                # Check first — avoids a DB error on re-runs for the common duplicate case.
                existing = await users_repo.get_user_by_name(user["user_name"])
                if not existing:
                    existing = await users_repo.get_user_by_email(user["email"])

                if existing:
                    user_id_to_internal[user["user_id"]] = existing["user_internal_id"]
                    logger.info(
                        f"User '{user.get('user_id')}' already exists "
                        f"(user_internal_id={existing['user_internal_id']}), skipping insert."
                    )
                    continue

                result = await users_repo.create_user(user)
                if result is None:
                    raise RuntimeError(f"create_user returned None for user '{user.get('user_id')}'")
                user_id_to_internal[user["user_id"]] = result["user_internal_id"]
            except Exception as e:
                pgcode = getattr(e, "pgcode", None)
                if pgcode and pgcode[:2] == "23":  # any remaining constraint violation — skip row
                    logger.warning(
                        f"Constraint violation (pgcode={pgcode}) for user '{user.get('user_id')}': {e} — skipping."
                    )
                else:
                    logger.error(f"Failed to create user '{user.get('user_id')}': {e}", exc_info=True)
                    raise
        return user_id_to_internal

    async def create_courses(self, courses: List[Dict[str, Any]]) -> int:
        """Create courses via the courses repository. Returns number of newly inserted courses."""
        count = 0
        for course in courses:
            try:
                # Check first — avoids a DB error on re-runs for the common duplicate case.
                existing = await courses_repo.list_courses_by_number(course["course_number"])
                if existing:
                    logger.info(
                        f"Course '{course.get('course_number')}' already exists, skipping insert."
                    )
                    continue

                result = await courses_repo.create_course(course)
                if result is None:
                    raise RuntimeError(f"create_course returned None for course '{course.get('course_number')}'")
                count += 1
            except Exception as e:
                pgcode = getattr(e, "pgcode", None)
                if pgcode and pgcode[:2] == "23":  # any remaining constraint violation — skip row
                    logger.warning(
                        f"Constraint violation (pgcode={pgcode}) for course '{course.get('course_number')}': {e} — skipping."
                    )
                else:
                    logger.error(f"Failed to create course '{course.get('course_number')}': {e}", exc_info=True)
                    raise
        return count

    async def create_offerings(
        self, offerings: List[Dict[str, Any]]
    ) -> Dict[Tuple[int, int, int, int], int]:
        """
        Create course offerings via the course_offering repository.
        Each offering dict may include a 'cohorts' key; cohorts are extracted and
        passed separately to create_course_offering which persists them atomically.

        Returns:
            Mapping of (course_number, academic_year, semester, group_number) -> offering_id,
            needed to resolve lecturer_courses FKs later.
        """
        offering_key_to_id: Dict[Tuple[int, int, int, int], int] = {}
        for offering in offerings:
            cohorts = offering.get("cohorts", [])
            data = {k: v for k, v in offering.items() if k != "cohorts"}
            key = (
                int(offering["course_number"]),
                int(offering["academic_year"]),
                int(offering["semester"]),
                int(offering["group_number"]),
            )
            try:
                # Check first — avoids a DB error on re-runs for the common duplicate case.
                existing = await offering_repo.list_course_offerings_by_group(*key)
                if existing:
                    offering_key_to_id[key] = existing["offering_id"]
                    logger.info(
                        f"Offering (course={key[0]}, year={key[1]}, sem={key[2]}, group={key[3]}) "
                        f"already exists (offering_id={existing['offering_id']}), skipping insert."
                    )
                    continue

                offering_id = await offering_repo.create_course_offering(data, cohorts)
                offering_key_to_id[key] = offering_id
            except Exception as e:
                pgcode = getattr(e, "pgcode", None)
                if pgcode == "23505":  # UNIQUE_VIOLATION race condition — fetch existing offering_id
                    existing = await offering_repo.list_course_offerings_by_group(*key)
                    if existing:
                        offering_key_to_id[key] = existing["offering_id"]
                        logger.info(
                            f"Offering (course={key[0]}, year={key[1]}, sem={key[2]}, group={key[3]}) "
                            f"already exists (offering_id={existing['offering_id']}), skipping insert."
                        )
                    else:
                        logger.warning(
                            f"UniqueViolation for offering (course={key[0]}, year={key[1]}, "
                            f"sem={key[2]}, group={key[3]}) but record not found — skipping."
                        )
                elif pgcode and pgcode[:2] == "23":  # CHECK, FK, NOT NULL, etc. — skip row
                    logger.warning(
                        f"Constraint violation (pgcode={pgcode}) for offering "
                        f"(course={key[0]}, year={key[1]}, sem={key[2]}, group={key[3]}): {e} — skipping."
                    )
                else:
                    logger.error(f"Failed to create offering for course '{offering.get('course_number')}': {e}", exc_info=True)
                    raise
        return offering_key_to_id

    async def create_lecturer_courses(
        self,
        lecturer_courses: List[Dict[str, Any]],
        user_id_to_internal: Dict[str, int],
        offering_key_to_id: Dict[Tuple[int, int, int, int], int],
    ) -> int:
        """
        Create lecturer-course links via the lecturer_courses repository.
        Resolves logical keys (user_id, course_number, year, semester, group)
        to internal FKs (lecturer_internal_id, offering_id) using the lookup maps
        built during user and offering creation.

        Returns:
            Number of lecturer-course links created.
        """
        count = 0
        for lc in lecturer_courses:
            lecturer_internal_id = user_id_to_internal.get(str(lc["user_id"]))
            key = (
                int(lc["course_number"]),
                int(lc["academic_year"]),
                int(lc["semester"]),
                int(lc["group_number"]),
            )
            offering_id = offering_key_to_id.get(key)

            if lecturer_internal_id is None or offering_id is None:
                logger.warning(
                    f"Skipping lecturer-course link: unresolvable FKs for "
                    f"user_id='{lc.get('user_id')}', course_number={lc.get('course_number')}, "
                    f"year={lc.get('academic_year')}, semester={lc.get('semester')}, "
                    f"group={lc.get('group_number')} "
                    f"(lecturer_internal_id={lecturer_internal_id}, offering_id={offering_id})"
                )
                continue

            try:
                result = await lc_repo.create_lecturer_course_upsert(
                    lecturer_internal_id, offering_id, "Lecturer"
                )
                if result is None:
                    raise RuntimeError(
                        f"create_lecturer_course_upsert returned None "
                        f"(lecturer={lecturer_internal_id}, offering={offering_id})"
                    )
                count += 1
            except Exception as e:
                pgcode = getattr(e, "pgcode", None)
                if pgcode and pgcode[:2] == "23":  # any constraint violation — skip row
                    logger.warning(
                        f"Constraint violation (pgcode={pgcode}) for lecturer-course link "
                        f"(lecturer={lecturer_internal_id}, offering={offering_id}): {e} — skipping."
                    )
                else:
                    logger.error(
                        f"Failed to create lecturer-course link "
                        f"(lecturer={lecturer_internal_id}, offering={offering_id}): {e}",
                        exc_info=True,
                    )
                    raise
        return count
    async def resolve_users_from_db(self, uids: List[str]) -> Dict[str, int]:
        """
        Look up existing users in the DB by user_name and return
        {user_id (str) -> user_internal_id (int)}.

        Used by load_assignments when users were already created in a prior
        load_static_data call and do not need to be re-inserted.
        Users not found in the DB are logged as warnings and skipped.
        """
        user_id_to_internal: Dict[str, int] = {}
        for uid in uids:
            try:
                result = await users_repo.get_user_by_user_id(uid)
                if result is None:
                    logger.warning(
                        f"User '{uid}' not found in DB — "
                        f"lecturer-course links for this user will be skipped"
                    )
                else:
                    user_id_to_internal[uid] = result["user_internal_id"]
            except Exception as e:
                logger.error(f"Failed to resolve user '{uid}' from DB: {e}", exc_info=True)
                raise
        return user_id_to_internal