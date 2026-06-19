# src/repositories/secretary_dashboard_queries.py

from typing import List, Dict, Any
from src.repositories.base import fetch_all, fetch_one

async def get_constraints_stats(semester_year: int, semester_number: int) -> Dict[str, Any]:
    """Get the amount of lecturers that have constraints in the semester"""
    sql = """
    WITH total_lecturers AS (
        SELECT COUNT(DISTINCT user_internal_id) as total 
        FROM users WHERE role = 'L'
    ),
    submitted_lecturers AS (
        SELECT COUNT(DISTINCT lecturer_internal_id) as submitted
        FROM lecturer_constraints
        WHERE semester_year = $1 AND semester_number = $2
    )
    SELECT total, submitted FROM total_lecturers, submitted_lecturers;
    """
    return await fetch_one(sql, semester_year, semester_number)

async def get_missing_constraints_lecturers(semester_year: int, semester_number: int) -> List[Dict[str, Any]]:
    """Get names and emails for lecturers that didn't submit constraints"""
    sql = """
    SELECT first_name, last_name, email
    FROM users
    WHERE role = 'L' AND user_internal_id NOT IN (
        SELECT lecturer_internal_id FROM lecturer_constraints
        WHERE semester_year = $1 AND semester_number = $2
    );
    """
    rows = await fetch_all(sql, semester_year, semester_number)
    return [dict(r) for r in rows]

async def get_approval_stats(schedule_id: int) -> Dict[str, Any]:
    """Get statistics about the amount of lecturers that didn't approve the schedule"""
    sql = """
    SELECT 
        status, 
        COUNT(*) as count
    FROM schedule_approvals
    WHERE schedule_id = $1
    GROUP BY status;
    """
    rows = await fetch_all(sql, schedule_id)

    return {row['status']: row['count'] for row in rows}

async def get_pending_lecturers(schedule_id: int) -> List[Dict[str, Any]]:
    """
    Returns names, emails, and status of lecturers whose approval is Pending
    (PEN or NULL) for the given schedule.
    """
    sql = """
    SELECT 
        u.first_name, 
        u.last_name, 
        u.email, 
        COALESCE(sa.status, 'PEN') AS status
    FROM users u
    LEFT JOIN schedule_approvals sa 
        ON u.user_internal_id = sa.lecturer_internal_id
        AND sa.schedule_id = $1
    WHERE u.role = 'L'
      AND (sa.status IS NULL OR sa.status = 'PEN')
    """
    rows = await fetch_all(sql, schedule_id)
    return [dict(r) for r in rows]


async def get_rejected_lecturers(schedule_id: int) -> List[Dict[str, Any]]:
    """
    Returns names, emails, and status of lecturers who rejected
    the given schedule.
    """
    sql = """
    SELECT 
        u.first_name, 
        u.last_name, 
        u.email, 
        sa.status
    FROM users u
    JOIN schedule_approvals sa 
        ON u.user_internal_id = sa.lecturer_internal_id
    WHERE u.role = 'L'
      AND sa.schedule_id = $1
      AND sa.status = 'REJ'
    """
    rows = await fetch_all(sql, schedule_id)
    return [dict(r) for r in rows]


async def get_total_lecturers_for_schedule(schedule_id: int) -> int:
    """
    Returns total number of lecturers that belong to a given schedule.
    """
    sql = """
    SELECT COUNT(DISTINCT cs.lecturer_internal_id) AS total
    FROM courses_schedules cs
    JOIN users u
        ON u.user_internal_id = cs.lecturer_internal_id
    WHERE u.role = 'L'
      AND cs.schedule_id = $1
    """
    row = await fetch_one(sql, schedule_id)
    return row["total"] if row else 0