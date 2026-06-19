from datetime import datetime
from typing import Optional, List, Any, Dict, Literal
from pydantic import BaseModel, Field, ConfigDict

from src.models.base import SchedulaBaseModel
from src.models.constraint import BrokenConstraintDetail

# Possible structured reasons for a failed solver run. ``None`` is also
# tolerated for backward-compatibility with rows persisted before this column
# was introduced.
FailureReason = Literal["user_constraints", "base_model", "data_infeasible"]

class BrokenConstraintRef(BaseModel):
    """Reference to a broken atomic constraint"""
    constraints_id: int
    atomic_index: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"constraints_id": 88, "atomic_index": 0}
        }
    )


class InfeasibleCohort(BaseModel):
    """A cohort whose required course hours exceed weekly capacity."""
    cohort: Dict[str, int] = Field(
        ...,
        description="The cohort identifier (target_department_id, target_year_level).",
    )
    required_hours: int
    available_hours: int
    course_count: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cohort": {"target_department_id": 202, "target_year_level": 1},
                "required_hours": 96,
                "available_hours": 67,
                "course_count": 37,
            }
        }
    )


class InfeasibleLecturer(BaseModel):
    """A lecturer whose required teaching hours exceed weekly capacity."""
    lecturer_internal_id: int
    required_hours: int
    available_hours: int


class SolverFailureDetails(BaseModel):
    """Structured payload for ``failure_reason == 'data_infeasible'`` runs."""
    infeasible_cohorts: List[InfeasibleCohort] = Field(default_factory=list)
    infeasible_lecturers: List[InfeasibleLecturer] = Field(default_factory=list)
    weekly_capacity_hours: Optional[int] = None


class SolverRunBase(SchedulaBaseModel):
    semester_year: int
    semester_number: int
    schedule_id: Optional[int] = None
    status: str = Field(..., pattern="^(pending|solved|failed)$")
    broken_constraints: Optional[List[BrokenConstraintRef]] = None
    failure_reason: Optional[FailureReason] = None
    failure_details: Optional[SolverFailureDetails] = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "semester_year": 2026,
                "semester_number": 1,
                "schedule_id": 10,
                "status": "solved",
                "broken_constraints": []
            }
        }
    )

class SolverRunCreate(SolverRunBase):
    pass

class SolverRunUpdate(BaseModel):
    schedule_id: Optional[int] = None
    status: Optional[str] = Field(None, pattern="^(pending|solved|failed)$")
    broken_constraints: Optional[List[BrokenConstraintRef]] = None
    failure_reason: Optional[FailureReason] = None
    failure_details: Optional[SolverFailureDetails] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "failed",
                "broken_constraints": [
                    {"constraints_id": 88, "atomic_index": 0}
                ],
                "completed_at": "2026-01-20T11:58:00Z"
            }
        }
    )

class SolverRun(SolverRunBase):
    run_id: int
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "run_id": 77,
                "semester_year": 2026,
                "semester_number": 1,
                "schedule_id": 10,
                "status": "solved",
                "broken_constraints": [],
                "created_at": "2026-01-20T11:45:00Z",
                "completed_at": "2026-01-20T11:58:00Z"
            }
        }
    )


class SolverStatusResponse(BaseModel):
    """Response model for solver status endpoint"""
    run_id: Optional[int] = None
    status: str = Field(..., description="Status: 'pending', 'solved', 'failed', or 'none'")
    schedule_id: Optional[int] = None
    broken_constraints: Optional[List[BrokenConstraintRef]] = None
    broken_constraint_details: Optional[List[BrokenConstraintDetail]] = None
    # Distinguishes the failure mode for 'failed' runs. Frontend uses this to
    # show the right call-to-action: a constraint conflict, a baseline-system
    # conflict (requires admin attention), or an over-subscribed dataset.
    failure_reason: Optional[FailureReason] = None
    failure_details: Optional[SolverFailureDetails] = None
    broken_constraints_count: Optional[int] = None
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    semester_year: int
    semester_number: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "run_id": 77,
                "status": "failed",
                "schedule_id": None,
                "broken_constraints": [
                    {"constraints_id": 88, "atomic_index": 0}
                ],
                "broken_constraint_details": [
                    {
                        "constraints_id": 88,
                        "raw_text": "No teaching on Thursday",
                        "lecturer_name": "Dana Levi"
                    }
                ],
                "failure_reason": "user_constraints",
                "broken_constraints_count": 1,
                "created_at": "2026-01-20T11:45:00Z",
                "completed_at": "2026-01-20T11:58:00Z",
                "semester_year": 2026,
                "semester_number": 1
            }
        }
    )