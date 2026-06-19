# src/input_convertor/mapper.py
"""Map Excel DataFrames to API payloads."""

import logging
import pandas as pd
from typing import List, Dict, Any, Tuple, Set
from . import config

logger = logging.getLogger(__name__)


# ── helpers ───────────────────────────────────────────────────────────────────

# Hebrew/English name fragments that mark a course row as non-classroom work
# (research projects, exemptions, paper writing, etc.). These rows should not
# get a scheduling slot — they exist only as catalogue entries for grading.
# Matching is substring-based and case-insensitive.
_NON_SCHEDULEABLE_NAME_FRAGMENTS = (
    # Hebrew
    "פטור",                    # exemption
    "השלמות פוסט-דוקטורט",      # post-doc supplements
    "השתלמות פוסט-דוקטורט",     # post-doc training
    "כתיבת עבודה",             # paper writing
    "עבודת גמר",               # final project / thesis
    "התנסות מחקרית",            # research experience
    "בקיאות במתמטיקה",         # math proficiency
    "הכרת הספרייה",            # library orientation
    "חרבות ברזל",              # special exemption (current events)
    # English
    "exemption",
    "research experience",
    "post-doctoral",
    "post-doc",
    "library orientation",
    "thesis",
    "final project",
    "paper writing",
)


def _is_scheduleable_course(course_name: str, credit_points: float) -> bool:
    """Return True if the course should participate in the solver.

    A course is non-scheduleable when:
    - credit_points <= 0 (e.g. exemption / research-only), OR
    - course_name matches any known non-scheduleable pattern, OR
    - credit_points >= 6 (final-project / thesis-style rows that don't fit a
      single weekly slot — Sun-Thu max is 12h, Fri 7h, but a 6+ CP item is
      research, not a lecture block).
    """
    if credit_points is None or credit_points <= 0:
        return False
    if credit_points >= 6:
        return False

    name_lower = (course_name or "").lower()
    for frag in _NON_SCHEDULEABLE_NAME_FRAGMENTS:
        if frag.lower() in name_lower:
            return False
    return True


def group_cohorts_by_course(cohorts: List[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
    """Index cohort list by course_number for fast lookup."""
    result: Dict[int, List[Dict[str, Any]]] = {}
    for c in cohorts:
        cn    = int(c["course_number"])
        entry = {"target_department_id": int(c["target_department_id"]), "target_year_level": int(c["target_year_level"])}
        result.setdefault(cn, [])
        if entry not in result[cn]:
            result[cn].append(entry)
    return result


# ── public mappers ────────────────────────────────────────────────────────────

def map_users_from_dedu(
    df: pd.DataFrame,
) -> List[Dict[str, Any]]:
    """Return deduplicated users list from the slim lecturers_dedu Excel.

    The dedu file contains only user identity columns (no course/semester data),
    so this is the preferred source for load_static_data.
    """
    C = config.LECTURERS_DEDU_COLUMNS
    required = [C[k] for k in ("user_id", "first_name", "last_name", "email", "department_id")]
    df = df.dropna(subset=required)

    users: List[Dict[str, Any]] = []
    seen: Set[str] = set()

    for _, row in df.iterrows():
        raw_user_name = str(row[C["user_id"]]).strip()

        # Use ID_NUMBER if present and non-empty, otherwise fall back to USER_ID.
        id_num_col = C.get("id_number")
        raw_id_num = row.get(id_num_col) if id_num_col and id_num_col in row.index else None
        if raw_id_num is not None and pd.notna(raw_id_num) and str(raw_id_num).strip():
            raw_user_id = str(raw_id_num).strip()
        else:
            raw_user_id = raw_user_name

        # Enforce DB CHECK (LENGTH(user_id) = 9): zero-pad to 9 digits.
        user_id = raw_user_id.zfill(9)
        user_name = raw_user_name

        if user_id not in seen:
            users.append({
                "user_id":       user_id,
                "user_name":     user_name,
                "first_name":    str(row[C["first_name"]]).strip(),
                "last_name":     str(row[C["last_name"]]).strip(),
                "email":         str(row[C["email"]]).strip(),
                "role":          config.LECTURER_ROLE,
                "department_id": int(row[C["department_id"]]),
            })
            seen.add(user_id)

    return users


def map_lecturers(
    df: pd.DataFrame,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return (users, offerings, lecturer_courses) from the lecturers Excel.

    Duplicate (user_id, course_number, academic_year, semester, group_number)
    rows in the source spreadsheet — common when the registrar's export has
    accidental repeats — are collapsed so the loader doesn't fight the
    DB UNIQUE constraint on lecturer_courses with constraint-violation churn.
    """
    C = config.LECTURERS_COLUMNS
    df = df.dropna(subset=[C[k] for k in ("user_id", "academic_year", "semester", "group_number", "course", "degree_level")])

    users: List[Dict[str, Any]] = []
    offerings: List[Dict[str, Any]] = []
    lecturer_courses: List[Dict[str, Any]] = []
    seen_users: Set[str] = set()
    seen_offerings: Set[Tuple[int, int, int, int]] = set()
    seen_lc: Set[Tuple[str, int, int, int, int]] = set()
    duplicate_lc_count = 0

    for _, row in df.iterrows():
        raw_user_name = str(row[C["user_id"]]).strip()

        # Use ID_NUMBER if present and non-empty, otherwise fall back to USER_ID.
        id_num_col = C.get("id_number")
        raw_id_num = row.get(id_num_col) if id_num_col and id_num_col in row.index else None
        if raw_id_num is not None and pd.notna(raw_id_num) and str(raw_id_num).strip():
            raw_user_id = str(raw_id_num).strip()
        else:
            raw_user_id = raw_user_name

        # Enforce the DB CHECK (LENGTH(user_id) = 9): zero-pad to 9 digits.
        # Excel stores numeric IDs as floats and drops leading zeros (e.g. 012345678 -> 12345678).
        user_id = raw_user_id.zfill(9)
        user_name = raw_user_name or user_id

        dept  = int(row[C["department_id"]])
        cn    = int(row[C["course"]])
        year  = int(row[C["academic_year"]])
        sem   = int(row[C["semester"]])
        group = int(row[C["group_number"]])

        if user_id not in seen_users:
            users.append({
                "user_id":       user_id,
                "user_name":     user_name,
                "first_name":    str(row[C["first_name"]]).strip(),
                "last_name":     str(row[C["last_name"]]).strip(),
                "email":         str(row[C["email"]]).strip(),
                "role":          config.LECTURER_ROLE,
                "department_id": dept,
            })
            seen_users.add(user_id)

        offering_key = (cn, year, sem, group)
        if offering_key not in seen_offerings:
            offerings.append({"course_number": cn, "academic_year": year, "semester": sem, "group_number": group})
            seen_offerings.add(offering_key)

        lc_key = (user_id, cn, year, sem, group)
        if lc_key in seen_lc:
            duplicate_lc_count += 1
            continue
        seen_lc.add(lc_key)
        lecturer_courses.append({"user_id": user_id, "course_number": cn, "academic_year": year, "semester": sem, "group_number": group})

    if duplicate_lc_count:
        logger.info(
            f"Skipped {duplicate_lc_count} duplicate lecturer_course rows during Excel import"
        )

    return users, offerings, lecturer_courses


def map_courses(
    df: pd.DataFrame,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return (courses, cohorts) from the courses Excel.

    Every row is a course. When Cohort_year is filled the row also carries a
    cohort target (which year-level of students this course is offered to).

    Each course gets an ``is_scheduleable`` flag derived from its name and
    credit points (see ``_is_scheduleable_course``). Cohort entries are
    suppressed for non-scheduleable courses so they do not contribute to
    cohort load in the solver. Sanity-check warnings are emitted for cohorts
    whose ``Cohort_year`` looks inconsistent with the course's degree level.
    """
    C          = config.COURSES_COLUMNS
    cohort_col = C["target_year_level"]
    required   = [C[k] for k in ("department", "degree_level", "course", "course_name", "credit_points")]

    courses: List[Dict[str, Any]] = []
    cohorts: List[Dict[str, Any]] = []
    seen: Set[int] = set()
    skipped_non_schedule = 0

    for _, row in df.dropna(subset=required).iterrows():
        dept  = int(row[C["department"]])
        level = int(row[C["degree_level"]])
        cn    = int(row[C["course"]])
        name  = str(row[C["course_name"]]).strip()
        cp    = float(row[C["credit_points"]])

        is_sched = _is_scheduleable_course(name, cp)

        if cn not in seen:
            courses.append({
                "course_number":   cn,
                "course_name":     name,
                "department_id":   dept,
                "degree_level":    level,
                "credit_points":   cp,
                "is_scheduleable": is_sched,
            })
            seen.add(cn)

        cohort_year = row[cohort_col]
        if pd.notna(cohort_year):
            if not is_sched:
                skipped_non_schedule += 1
                continue

            try:
                year_int = int(cohort_year)
            except (TypeError, ValueError):
                logger.warning(
                    f"Course {cn} ({name!r}) has non-integer Cohort_year={cohort_year!r}; skipping cohort entry"
                )
                continue

            # Sanity check: undergraduate (degree_level=1) typically year 1-4,
            # graduate (degree_level >= 2) typically year 1-3.
            if year_int < 1 or year_int > 4:
                logger.warning(
                    f"Course {cn} ({name!r}) has out-of-range Cohort_year={year_int} (expected 1-4); skipping cohort entry"
                )
                continue

            entry = {"course_number": cn, "target_department_id": dept, "target_year_level": year_int}
            if entry not in cohorts:
                cohorts.append(entry)

    if skipped_non_schedule:
        logger.info(
            f"Suppressed {skipped_non_schedule} cohort entries for non-scheduleable courses "
            f"(0-CP, final projects, exemptions, etc.)"
        )

    return courses, cohorts
