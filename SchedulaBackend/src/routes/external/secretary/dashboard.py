from fastapi import APIRouter, Request, HTTPException, status, Query
from typing import List, Optional, Dict, Any
from src.repositories import semesters as semesters_repo
from src.repositories import dashboard_queries as dash_repo
from src.repositories import schedules as schedules_repo
from src.repositories import solver_runs as solver_runs_repo
from src.models.semester import SemesterBase
from src.models.solver_run import SolverStatusResponse
from src.models.constraint import BrokenConstraintDetail
import logging
logger = logging.getLogger(__name__)

router = APIRouter()



@router.get(
    "/semester_info",
    response_model=SemesterBase,
    responses={
        200: {
            "description": "Returns general information about the active semester.",
            "content": {"application/json": {"example": {
                "semester_year": 2026,
                "semester_number": 1,
                "semester_start_date": "2026-03-01",
                "semester_end_date": "2026-06-30",
                "constraint_start_date": "2025-12-01",
                "constraint_end_date": "2026-01-30",
                "change_period_start": "2026-02-15",
                "change_period_end": "2026-03-15",
                "status": "SUB"
            }}}
        },
        403: {"description": "Forbidden - Admin/Secretary access required."},
        404: {"description": "No active semester found."}
    }
)
async def get_active_semester_info(
        request: Request
):
    """
    Returns general information about the current active semester:
    dates, deadlines, and current workflow status.
    """
    semester = await semesters_repo.get_current_semester()
    if not semester:
        raise HTTPException(status_code=404, detail="No active semester found")
    return semester



@router.get(
    "/stats",
    response_model=Dict[str, Any],
    responses={
        200: {
            "description": "Returns statistics based on the current semester status.",
            "content": {"application/json": {"examples": {
                "constraints_period": {
                    "summary": "Example during SUB status",
                    "value": {
                        "type": "constraints",
                        "total_lecturers": 50,
                        "submitted_count": 35,
                        "missing_lecturers": [
                            {"first_name": "Alice", "last_name": "Smith", "email": "alice@univ.edu"}
                        ]
                    }
                },
                "approval_period": {
                    "summary": "Example during CHA/PUB status",
                    "value": {
                        "type": "approvals",
                        "schedule_id": 42,
                        "approved": 20,
                        "rejected": 5,
                        "pending": 25,
                        "pending_lecturers": [
                            {"first_name": "Bob", "last_name": "Jones", "email": "bob@univ.edu", "status": "PEN"}
                        ],
                        "rejected_lecturers": [
                            {"first_name": "John", "last_name": "Doe", "email": "johnd@univ.edu", "status": "REJ"}
                        ]
                    }
                }
            }}}
        },
        403: {"description": "Forbidden - Admin/Secretary access required."},
        404: {"description": "No active semester found."}
    }
)
async def get_semester_stats(
        request: Request
):
    """
    Returns lecturer distribution statistics based on the current semester status.
    Used to monitor lecturer engagement (submissions or approvals).
    """
    semester = await semesters_repo.get_current_semester()
    if not semester:
        raise HTTPException(status_code=404, detail="No active semester found")

    year = semester['semester_year']
    num = semester['semester_number']
    sem_status = semester['status']

    if sem_status == 'SUB':
        stats = await dash_repo.get_constraints_stats(year, num)
        missing = await dash_repo.get_missing_constraints_lecturers(year, num)
        return {
            "type": "constraints",
            "total_lecturers": stats['total'],
            "submitted_count": stats['submitted'],
            "missing_lecturers": missing
        }

    elif sem_status in ['CHA']:
        latest_sched = await schedules_repo.get_latest_schedule_for_semester(year, num)
        if latest_sched:
            sched_id = latest_sched['schedule_id']
            total_lecturers = await dash_repo.get_total_lecturers_for_schedule(sched_id)
            app_stats = await dash_repo.get_approval_stats(sched_id)
            pending = await dash_repo.get_pending_lecturers(sched_id)
            rejected = await dash_repo.get_rejected_lecturers(sched_id)
            return {
                "type": "approvals",
                "schedule_id": sched_id,
                "total_lecturers": total_lecturers,
                "approved": app_stats.get('APP', 0),
                "rejected": len(rejected),
                "pending": len(pending),
                "pending_lecturers": pending,
                "rejected_lecturers": rejected
            }

    return {"type": "none", "message": "No statistics available for current status"}


@router.get(
    "/solver_status",
    status_code=status.HTTP_200_OK,
    response_model=SolverStatusResponse,
    responses={
        200: {
            "description": "Returns the simplified solver run status for the semester.",
            "content": {"application/json": {"examples": {
                "pending": {
                    "summary": "Solver is currently running",
                    "value": {
                        "run_id": 15,
                        "status": "pending",
                        "schedule_id": None,
                        "broken_constraints_count": 0,
                        "semester_year": 2026,
                        "semester_number": 1
                    }
                },
                "failed_user_constraints": {
                    "summary": "Solver failed because lecturer constraints conflict",
                    "value": {
                        "run_id": 15,
                        "status": "failed",
                        "schedule_id": None,
                        "broken_constraints_count": 2,
                        "failure_reason": "user_constraints",
                        "semester_year": 2026,
                        "semester_number": 1
                    }
                },
                "failed_data_infeasible": {
                    "summary": "Solver failed because the dataset is over-subscribed",
                    "value": {
                        "run_id": 16,
                        "status": "failed",
                        "schedule_id": None,
                        "broken_constraints_count": 0,
                        "failure_reason": "data_infeasible",
                        "failure_details": {
                            "infeasible_cohorts": [
                                {
                                    "cohort": {"target_department_id": 202, "target_year_level": 1},
                                    "required_hours": 96,
                                    "available_hours": 67,
                                    "course_count": 37
                                }
                            ],
                            "infeasible_lecturers": [],
                            "weekly_capacity_hours": 67
                        },
                        "semester_year": 2026,
                        "semester_number": 1
                    }
                },
                "failed_base_model": {
                    "summary": "Solver failed because system hard constraints alone are unsat",
                    "value": {
                        "run_id": 17,
                        "status": "failed",
                        "schedule_id": None,
                        "broken_constraints_count": 0,
                        "failure_reason": "base_model",
                        "semester_year": 2026,
                        "semester_number": 1
                    }
                }
            }}},
        }
    },
)
async def get_solver_status(
        request: Request,
        semester_year: int = Query(..., description="The semester year to check solver status for"),
        semester_number: int = Query(..., ge=1, le=3, description="The semester number (1-3)"),
) -> SolverStatusResponse:
    """
    Returns the simplified solver status (success/failure and count only).
    Used by lecturers to check if their new constraints caused a global failure.
    """
    try:
        # 1. Fetch the latest run from the repository
        latest_run = await solver_runs_repo.get_latest_run(semester_year, semester_number)

        if not latest_run:
            return SolverStatusResponse(
                run_id=None,
                status="none",
                broken_constraints_count=0,
                semester_year=semester_year,
                semester_number=semester_number
            )

        # 2. Extract broken constraints to determine the count
        broken_constraints = latest_run.get("broken_constraints") or []
        if isinstance(broken_constraints, str):
            import json
            broken_constraints = json.loads(broken_constraints)

        # 3. Failure metadata (introduced alongside the data-infeasibility
        # pre-flight check) — lets the dashboard render an actionable message
        # for non-conflict failures without forcing the frontend to guess.
        failure_details = latest_run.get("failure_details")
        if isinstance(failure_details, str):
            import json
            try:
                failure_details = json.loads(failure_details)
            except (TypeError, ValueError):
                failure_details = None

        return SolverStatusResponse(
            run_id=latest_run.get("run_id"),
            status=latest_run.get("status"),
            schedule_id=latest_run.get("schedule_id"),
            broken_constraints_count=len(broken_constraints),
            failure_reason=latest_run.get("failure_reason"),
            failure_details=failure_details,
            created_at=latest_run.get("created_at"),
            completed_at=latest_run.get("completed_at"),
            semester_year=semester_year,
            semester_number=semester_number
        )

    except Exception as e:
        logger.error(f"Error fetching solver status: {str(e)}", exc_info=True) #
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while fetching status"
        )

