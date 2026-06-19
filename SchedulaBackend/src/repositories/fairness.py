"""Fairness aggregation.

Computes per-lecturer atomic-constraint coverage against the latest (or a
caller-specified) schedule of a semester. Reuses existing repositories so
the only new SQL here is the lecturer + course-count query.
"""

from typing import Any, Dict, List, Optional, Set, Tuple

from src.repositories import breaking_constraints as breaking_constraints_repo
from src.repositories import constraints as constraints_repo
from src.repositories.base import fetch_all


async def _fetch_lecturers_with_course_counts(
    semester_year: int,
    semester_number: int,
) -> List[Dict[str, Any]]:
    """Return every lecturer (role='L') with the number of distinct course
    offerings they're assigned to for the given semester.

    Lecturers with no offerings for the semester still appear with
    ``courses_count = 0`` so the fairness page lists every lecturer.
    """
    sql = """
        SELECT
            u.user_internal_id AS lecturer_internal_id,
            u.first_name,
            u.last_name,
            COUNT(DISTINCT co.offering_id) AS courses_count
        FROM users u
        LEFT JOIN lecturer_courses lc
            ON lc.lecturer_internal_id = u.user_internal_id
        LEFT JOIN course_offering co
            ON co.offering_id = lc.offering_id
           AND co.academic_year = $1
           AND co.semester = $2
        WHERE u.role = 'L'
        GROUP BY u.user_internal_id, u.first_name, u.last_name
        ORDER BY u.last_name, u.first_name
    """
    rows = await fetch_all(sql, semester_year, semester_number)
    return [dict(r) for r in rows]


def _resolve_is_hard(
    atomic: Dict[str, Any],
    secretary_override_as_hard: Optional[bool],
) -> bool:
    """Decide whether an atomic counts as HARD given override + priority."""
    if secretary_override_as_hard is not None:
        return bool(secretary_override_as_hard)
    priority = str(atomic.get("priority", "soft")).lower()
    return priority == "hard"


def _build_broken_index_map(
    breaking_rows: List[Dict[str, Any]],
) -> Dict[int, Set[int]]:
    """Map ``constraints_id -> {atomic_constraint_index, ...}``.

    `breaking_constraints_repo.list_by_schedule` already parses the JSONB
    column into Python lists, but we tolerate either shape defensively.
    """
    out: Dict[int, Set[int]] = {}
    for row in breaking_rows:
        cid = row.get("constraints_id")
        if cid is None:
            continue
        atomics = row.get("breaking_atomic_constraints") or []
        indices: Set[int] = set()
        if isinstance(atomics, list):
            for a in atomics:
                if not isinstance(a, dict):
                    continue
                idx = a.get("atomic_constraint_index")
                if isinstance(idx, int):
                    indices.add(idx)
        if indices:
            existing = out.setdefault(cid, set())
            existing.update(indices)
    return out


async def _load_constraint_rows(
    schedule_id: Optional[int],
    semester_year: int,
    semester_number: int,
) -> Tuple[List[Dict[str, Any]], bool]:
    """Return constraint rows used for the given schedule.

    Prefer rows linked via ``schedule_id``. Fall back to all rows for the
    semester when none of them are linked (older data that predates the
    ``schedule_id`` column being populated).

    Returns a tuple ``(rows, used_schedule_scope)`` where
    ``used_schedule_scope`` is ``True`` when the rows came from the
    schedule-scoped query and ``False`` when the semester fallback was used.
    The caller uses this flag to load breaking constraints from the matching
    scope so the two sides never disagree.
    """
    if schedule_id is not None:
        rows = await constraints_repo.list_constraints_by_schedule(schedule_id)
        if rows:
            return rows, True
    rows = await constraints_repo.list_constraints_by_semester(
        semester_year, semester_number
    )
    return rows, False


def _aggregate_atomics(
    constraints_rows: List[Dict[str, Any]],
    broken_index_by_cid: Dict[int, Set[int]],
) -> Tuple[
    Dict[int, Dict[str, int]],
    Dict[int, List[Dict[str, Any]]],
]:
    """Walk every atomic and aggregate per-lecturer stats + detail rows.

    Returns a tuple ``(stats_by_lecturer, details_by_lecturer)`` where:
    - ``stats_by_lecturer`` maps ``lecturer_internal_id`` to a dict with
      keys ``total_atomics``, ``broken_atomics``, ``satisfied_atomics``,
      ``hard_total``, ``soft_total``, ``hard_broken``, ``soft_broken``.
    - ``details_by_lecturer`` maps ``lecturer_internal_id`` to a list of
      atomic detail dicts (one entry per atomic constraint).
    """
    stats: Dict[int, Dict[str, int]] = {}
    details: Dict[int, List[Dict[str, Any]]] = {}

    for row in constraints_rows:
        lecturer_id = row.get("lecturer_internal_id")
        if lecturer_id is None:
            continue
        cid = row.get("constraints_id")
        override = row.get("secretary_override_as_hard")
        structured = row.get("structured_rules") or {}
        atomics = structured.get("atomic_constraints") if isinstance(structured, dict) else None
        if not isinstance(atomics, list):
            continue
        broken_indices = broken_index_by_cid.get(cid, set()) if cid is not None else set()

        lec_stats = stats.setdefault(
            lecturer_id,
            {
                "total_atomics": 0,
                "broken_atomics": 0,
                "satisfied_atomics": 0,
                "hard_total": 0,
                "soft_total": 0,
                "hard_broken": 0,
                "soft_broken": 0,
            },
        )
        lec_details = details.setdefault(lecturer_id, [])

        for idx, atomic in enumerate(atomics):
            if not isinstance(atomic, dict):
                continue
            is_hard = _resolve_is_hard(atomic, override)
            is_broken = idx in broken_indices

            lec_stats["total_atomics"] += 1
            if is_hard:
                lec_stats["hard_total"] += 1
            else:
                lec_stats["soft_total"] += 1
            if is_broken:
                lec_stats["broken_atomics"] += 1
                if is_hard:
                    lec_stats["hard_broken"] += 1
                else:
                    lec_stats["soft_broken"] += 1
            else:
                lec_stats["satisfied_atomics"] += 1

            lec_details.append(
                {
                    "constraints_id": cid,
                    "raw_text": row.get("raw_text"),
                    "atomic_index": idx,
                    "type": atomic.get("type"),
                    "days": atomic.get("days") or [],
                    "time_slot": atomic.get("time_slot"),
                    "is_hard": is_hard,
                    "is_broken": is_broken,
                }
            )

    return stats, details


def _compute_score(stats: Dict[str, int]) -> float:
    """Weighted score: hard breaks penalise the most, soft breaks half as much.

    score = (satisfied + 0.5 * soft_broken) / max(total, 1)
    """
    total = stats.get("total_atomics", 0)
    if total <= 0:
        return 1.0
    satisfied = stats.get("satisfied_atomics", 0)
    soft_broken = stats.get("soft_broken", 0)
    return round((satisfied + 0.5 * soft_broken) / total, 4)


async def compute_lecturer_fairness(
    semester_year: int,
    semester_number: int,
    schedule_id: Optional[int],
) -> List[Dict[str, Any]]:
    """Aggregate atomic-constraint coverage per lecturer for a schedule.

    Args:
        semester_year: Academic year.
        semester_number: Semester number (1-3).
        schedule_id: Optional schedule scope. When ``None`` the caller has
            decided there is no schedule yet; we still return every
            lecturer with zeroed counts.

    Returns:
        A list of per-lecturer dicts ready for serialization. One entry
        per lecturer in the system (``users.role = 'L'``), even when the
        lecturer has no constraints or no broken atomics.
    """
    lecturer_rows = await _fetch_lecturers_with_course_counts(
        semester_year, semester_number
    )

    if schedule_id is None:
        constraints_rows: List[Dict[str, Any]] = []
        breaking_rows: List[Dict[str, Any]] = []
    else:
        constraints_rows, used_schedule_scope = await _load_constraint_rows(
            schedule_id, semester_year, semester_number
        )
        # Load breaking constraints from the SAME scope the constraints came
        # from. If the constraint rows fell back to the semester (because none
        # were linked to this schedule), the schedule-scoped breaking query
        # would return nothing and every atomic would look satisfied. Matching
        # the scope keeps the broken/satisfied split correct.
        if used_schedule_scope:
            breaking_rows = await breaking_constraints_repo.list_by_schedule(
                schedule_id
            )
        else:
            breaking_rows = await breaking_constraints_repo.list_by_semester(
                semester_year, semester_number
            )

    broken_index_by_cid = _build_broken_index_map(breaking_rows)
    stats_by_lecturer, details_by_lecturer = _aggregate_atomics(
        constraints_rows, broken_index_by_cid
    )

    results: List[Dict[str, Any]] = []
    for lec in lecturer_rows:
        lecturer_id = lec["lecturer_internal_id"]
        stats = stats_by_lecturer.get(
            lecturer_id,
            {
                "total_atomics": 0,
                "broken_atomics": 0,
                "satisfied_atomics": 0,
                "hard_total": 0,
                "soft_total": 0,
                "hard_broken": 0,
                "soft_broken": 0,
            },
        )
        first = lec.get("first_name") or ""
        last = lec.get("last_name") or ""
        full_name = f"{first} {last}".strip() or f"Lecturer #{lecturer_id}"

        results.append(
            {
                "lecturer_internal_id": lecturer_id,
                "lecturer_name": full_name,
                "courses_count": int(lec.get("courses_count") or 0),
                **stats,
                "fairness_score": _compute_score(stats),
                "is_fair": stats["hard_broken"] == 0,
                "atomic_details": details_by_lecturer.get(lecturer_id, []),
            }
        )

    return results
