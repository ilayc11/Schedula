from typing import Dict, List, Optional, Any
import json
from src.repositories.base import execute, fetch_one, fetch_all

TABLE = "solver_runs"
ID_COL = "run_id"


def _deserialize_solver_run(rec: Dict[str, Any]) -> Dict[str, Any]:
    """Helper to deserialize JSONB fields from database record."""
    if rec and 'broken_constraints' in rec and rec['broken_constraints'] is not None:
        # If it's a string, parse it; otherwise it's already a list
        if isinstance(rec['broken_constraints'], str):
            rec['broken_constraints'] = json.loads(rec['broken_constraints'])
    if rec and 'failure_details' in rec and rec['failure_details'] is not None:
        if isinstance(rec['failure_details'], str):
            rec['failure_details'] = json.loads(rec['failure_details'])
    return rec


async def create_run(semester_year: int, semester_number: int) -> Optional[Dict[str, Any]]:
    """
    Create a new pending solver run for a semester.
    """
    sql = f"""
        INSERT INTO {TABLE} (semester_year, semester_number, status)
        VALUES ($1, $2, 'pending')
        RETURNING *
    """
    rec = await fetch_one(sql, semester_year, semester_number)
    return dict(rec) if rec else None


async def update_run_success(
    run_id: int, 
    schedule_id: int
) -> Optional[Dict[str, Any]]:
    """
    Update a solver run to mark it as successfully solved.
    """
    sql = f"""
        UPDATE {TABLE}
        SET status = 'solved', 
            schedule_id = $2,
            completed_at = CURRENT_TIMESTAMP
        WHERE {ID_COL} = $1
        RETURNING *
    """
    rec = await fetch_one(sql, run_id, schedule_id)
    return _deserialize_solver_run(dict(rec)) if rec else None


async def update_run_failure(
    run_id: int,
    broken_constraints: List[Dict[str, int]],
    failure_reason: Optional[str] = None,
    failure_details: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Update a solver run to mark it as failed.

    ``failure_reason`` distinguishes the failure mode reported by the solver
    (``user_constraints``, ``base_model``, or ``data_infeasible``) and
    ``failure_details`` carries the structured payload (e.g. infeasible
    cohorts/lecturers) for ``data_infeasible`` runs. Both are persisted as
    JSONB / VARCHAR on ``solver_runs`` so the dashboard can render an
    actionable message.
    """
    sql = f"""
        UPDATE {TABLE}
        SET status = 'failed',
            broken_constraints = $2::jsonb,
            failure_reason = $3,
            failure_details = $4::jsonb,
            completed_at = CURRENT_TIMESTAMP
        WHERE {ID_COL} = $1
        RETURNING *
    """
    rec = await fetch_one(
        sql,
        run_id,
        json.dumps(broken_constraints),
        failure_reason,
        json.dumps(failure_details) if failure_details else None,
    )
    return _deserialize_solver_run(dict(rec)) if rec else None


async def update_run_by_semester(
    semester_year: int,
    semester_number: int,
    status: str,
    schedule_id: Optional[int] = None,
    broken_constraints: Optional[List[Dict[str, int]]] = None,
    failure_reason: Optional[str] = None,
    failure_details: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Update the latest pending solver run for a semester.
    Used by the RabbitMQ consumer when it receives a solver response.
    """
    # Find the latest pending run for this semester
    find_sql = f"""
        SELECT {ID_COL} FROM {TABLE}
        WHERE semester_year = $1 AND semester_number = $2 AND status = 'pending'
        ORDER BY created_at DESC
        LIMIT 1
    """
    rec = await fetch_one(find_sql, semester_year, semester_number)
    
    if not rec:
        return None
    
    run_id = rec[ID_COL]
    
    if status == 'solved':
        return await update_run_success(run_id, schedule_id)
    elif status == 'failed':
        return await update_run_failure(
            run_id,
            broken_constraints or [],
            failure_reason=failure_reason,
            failure_details=failure_details,
        )

    return None


async def get_run(run_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a solver run by ID.
    """
    sql = f"SELECT * FROM {TABLE} WHERE {ID_COL} = $1"
    rec = await fetch_one(sql, run_id)
    return _deserialize_solver_run(dict(rec)) if rec else None


async def get_latest_run(semester_year: int, semester_number: int) -> Optional[Dict[str, Any]]:
    """
    Get the most recent solver run for a semester.
    """
    sql = f"""
        SELECT * FROM {TABLE}
        WHERE semester_year = $1 AND semester_number = $2
        ORDER BY created_at DESC
        LIMIT 1
    """
    rec = await fetch_one(sql, semester_year, semester_number)
    return _deserialize_solver_run(dict(rec)) if rec else None


async def list_runs_by_semester(semester_year: int, semester_number: int) -> List[Dict[str, Any]]:
    """
    List all solver runs for a semester, ordered by most recent first.
    """
    sql = f"""
        SELECT * FROM {TABLE}
        WHERE semester_year = $1 AND semester_number = $2
        ORDER BY created_at DESC
    """
    rows = await fetch_all(sql, semester_year, semester_number)
    return [_deserialize_solver_run(dict(r)) for r in rows]


async def get_broken_constraint_details(
    semester_year: int, 
    semester_number: int
) -> List[Dict[str, Any]]:
    """
    Get details of broken constraints from the latest failed run.
    Joins with lecturer_constraints to get the raw_text for display.
    """
    sql = """
        SELECT 
            lc.constraints_id,
            lc.raw_text,
            lc.lecturer_internal_id,
            u.first_name || ' ' || u.last_name as lecturer_name
        FROM solver_runs sr
        CROSS JOIN LATERAL jsonb_array_elements(sr.broken_constraints) AS bc(constraint_obj)
        JOIN lecturer_constraints lc ON lc.constraints_id = (bc.constraint_obj->>'constraints_id')::bigint
        JOIN users u ON u.user_internal_id = lc.lecturer_internal_id
        WHERE sr.semester_year = $1 
          AND sr.semester_number = $2 
          AND sr.status = 'failed'
        ORDER BY sr.created_at DESC
        LIMIT 10
    """
    rows = await fetch_all(sql, semester_year, semester_number)
    return [dict(r) for r in rows]


async def get_all_runs() -> List[Dict[str, Any]]:
    """
    Get all solver runs.
    """
    sql = f"SELECT * FROM {TABLE} ORDER BY created_at DESC"
    recs = await fetch_all(sql)
    return [_deserialize_solver_run(dict(rec)) for rec in recs]


async def delete_run(run_id: int) -> bool:
    """
    Delete a solver run by ID.
    """
    sql = f"DELETE FROM {TABLE} WHERE {ID_COL} = $1 RETURNING {ID_COL}"
    rec = await fetch_one(sql, run_id)
    return bool(rec)

