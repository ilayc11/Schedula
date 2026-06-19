"""Secretary-only fairness endpoint.

Reports per-lecturer atomic-constraint coverage against the latest
schedule of a semester (or a caller-specified schedule).
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Path, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field

from src.repositories import fairness as fairness_repo
from src.repositories import schedules as schedules_repo

logger = logging.getLogger(__name__)
router = APIRouter()


class AtomicDetail(BaseModel):
    constraints_id: Optional[int] = None
    raw_text: Optional[str] = None
    atomic_index: int
    type: Optional[str] = None
    days: List[int] = Field(default_factory=list)
    time_slot: Optional[Dict[str, Any]] = None
    is_hard: bool
    is_broken: bool


class LecturerFairness(BaseModel):
    lecturer_internal_id: int
    lecturer_name: str
    courses_count: int
    total_atomics: int
    broken_atomics: int
    satisfied_atomics: int
    hard_total: int
    soft_total: int
    hard_broken: int
    soft_broken: int
    fairness_score: float
    is_fair: bool
    atomic_details: List[AtomicDetail] = Field(default_factory=list)


class FairnessResponse(BaseModel):
    status: str
    semester_year: int
    semester_number: int
    schedule_id: Optional[int]
    schedule_status: str  # "draft" | "published" | "none"
    data: List[LecturerFairness]
    count: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "success",
                "semester_year": 2026,
                "semester_number": 1,
                "schedule_id": 12,
                "schedule_status": "published",
                "data": [
                    {
                        "lecturer_internal_id": 101,
                        "lecturer_name": "Dana Cohen",
                        "courses_count": 3,
                        "total_atomics": 5,
                        "broken_atomics": 2,
                        "satisfied_atomics": 3,
                        "hard_total": 3,
                        "soft_total": 2,
                        "hard_broken": 1,
                        "soft_broken": 1,
                        "fairness_score": 0.7,
                        "is_fair": False,
                        "atomic_details": [
                            {
                                "constraints_id": 42,
                                "raw_text": "I cannot teach on Mondays 16-20",
                                "atomic_index": 0,
                                "type": "block",
                                "days": [2],
                                "time_slot": {"start_hour": 16, "end_hour": 20},
                                "is_hard": True,
                                "is_broken": True,
                            }
                        ],
                    }
                ],
                "count": 1,
            }
        }
    )


def _schedule_status_label(schedule: Optional[Dict[str, Any]]) -> str:
    if not schedule:
        return "none"
    if schedule.get("is_published"):
        return "published"
    if schedule.get("is_draft"):
        return "draft"
    return "none"


@router.get(
    "/{semester_year}/{semester_number}",
    status_code=status.HTTP_200_OK,
    response_model=FairnessResponse,
    responses={
        200: {
            "description": "Per-lecturer fairness report for the latest schedule of the semester.",
        },
        403: {
            "description": "Forbidden - User is not a Secretary",
            "content": {
                "application/json": {
                    "example": {"detail": "Only secretaries can view fairness reports"}
                }
            },
        },
    },
)
async def get_lecturer_fairness_report(
    request: Request,
    semester_year: int = Path(..., ge=2000, le=2100, description="Semester year"),
    semester_number: int = Path(..., ge=1, le=3, description="Semester number"),
    schedule_id: Optional[int] = Query(
        None,
        description="Optional schedule override. Defaults to the latest schedule "
                    "for the semester (published if any, else most recent draft).",
    ),
) -> FairnessResponse:
    """Return per-lecturer atomic-constraint coverage for a schedule.

    For each lecturer the response includes:
    - total / broken / satisfied atomic counts,
    - hard vs soft breakdown,
    - a weighted ``fairness_score`` (1.0 = perfect, hard breaks penalised more
      than soft breaks),
    - ``atomic_details`` with each atomic's day/time/type and is_broken flag.

    If no schedule exists yet for the semester, the endpoint still returns
    every lecturer with zeroed counts and ``schedule_status = "none"``.
    """
    user_role = request.state.user_role
    if user_role != "S":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only secretaries can view fairness reports",
        )

    try:
        resolved_schedule: Optional[Dict[str, Any]] = None
        if schedule_id is not None:
            resolved_schedule = await schedules_repo.get_schedule(schedule_id)
            if resolved_schedule is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Schedule ID {schedule_id} not found.",
                )
            if (
                resolved_schedule.get("semester_year") != semester_year
                or resolved_schedule.get("semester_number") != semester_number
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Schedule does not belong to the given semester.",
                )
        else:
            resolved_schedule = await schedules_repo.get_latest_schedule_for_semester(
                semester_year, semester_number
            )

        resolved_schedule_id = (
            resolved_schedule.get("schedule_id") if resolved_schedule else None
        )
        schedule_status = _schedule_status_label(resolved_schedule)

        data = await fairness_repo.compute_lecturer_fairness(
            semester_year=semester_year,
            semester_number=semester_number,
            schedule_id=resolved_schedule_id,
        )

        return FairnessResponse(
            status="success",
            semester_year=semester_year,
            semester_number=semester_number,
            schedule_id=resolved_schedule_id,
            schedule_status=schedule_status,
            data=data,
            count=len(data),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Error computing fairness report for %s/%s: %s",
            semester_year,
            semester_number,
            exc,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compute fairness report: {exc}",
        )
