from datetime import datetime
from typing import Optional, Any, Dict, List

from pydantic import BaseModel, Field, ConfigDict

from src.models.base import SchedulaBaseModel


class ConstraintBase(SchedulaBaseModel):
    """Base model for constraints entered by users"""
    lecturer_internal_id: int = Field(description="User who entered the constraint (FK to users.user_internal_id)")
    schedule_id: Optional[int] = Field(None, description="Schedule ID (FK to schedules.schedule_id)")
    semester_year: int = Field(..., ge=2000, le=2100, description="Semester year (FK to semesters.semester_year)")
    semester_number: int = Field(..., ge=1, le=3, description="Semester number (FK to semesters.semester_number)")
    raw_text: Optional[str] = Field(None, description="Original text of the constraint")
    structured_rules: Optional[Any] = Field(None, description="Structured JSON rules for the constraint")
    secretary_override_as_hard: Optional[bool] = Field(None, description="Secretary override: NULL=use atomic priority, True=force all hard, False=force all soft")
    is_manually_edited: Optional[bool] = Field(False, description="True when a secretary has edited this constraint's structured_rules")
    original_raw_text: Optional[str] = Field(None, description="Lecturer's original raw_text before the secretary edit; null if never edited")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "lecturer_internal_id": 42,
                "schedule_id": 10,
                "semester_year": 2026,
                "semester_number": 1,
                "raw_text": "I cannot teach on Sundays before 10:00.",
                "structured_rules": {
                    "atomic_constraints": [
                        {
                            "type": "block",
                            "days": [1],
                            "time_slot": {"start_hour": 8, "end_hour": 10},
                            "priority": "soft"
                        }
                    ]
                },
                "secretary_override_as_hard": None,
                "is_manually_edited": False,
                "original_raw_text": None
            }
        }
    )



class ConstraintCreate(ConstraintBase):
    """Model for creating a new constraint"""
    pass


class ConstraintUpdate(BaseModel):
    """Model for updating an existing constraint"""
    raw_text: Optional[str] = None
    structured_rules: Optional[Any] = None
    last_updated_at: Optional[datetime] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "raw_text": "Prefer no classes on Tuesday afternoons.",
                "structured_rules": {
                    "atomic_constraints": [
                        {
                            "type": "block",
                            "days": [3],
                            "time_slot": {"start_hour": 14, "end_hour": 20},
                            "priority": "soft"
                        }
                    ]
                }
            }
        }
    )


class ConstraintResponse(ConstraintBase):
    """Response model for returning constraint data"""
    pass

class ConstraintPreviewPayload(BaseModel):
    raw_text: str = Field(..., description="The free text constraint entered by the user.")
    semester_year: int
    semester_number: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "raw_text": "I am unavailable on Friday.",
                "semester_year": 2026,
                "semester_number": 1
            }
        }
    )

class ConstraintSavePayload(BaseModel):
    """Payload model for saving the constraint confirmed by the user (no lecturer_internal_id required)."""
    schedule_id: Optional[int] = Field(None, description="Schedule ID (FK to schedules.schedule_id)")
    semester_year: int = Field(..., ge=2000, le=2100, description="Semester year (FK to semesters.semester_year)")
    semester_number: int = Field(..., ge=1, le=3, description="Semester number (FK to semesters.semester_number)")
    raw_text: Optional[str] = Field(None, description="Original text of the constraint")
    structured_rules: Optional[Any] = Field(None, description="Structured JSON rules for the constraint")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "schedule_id": 10,
                "semester_year": 2026,
                "semester_number": 1,
                "raw_text": "I cannot teach after 17:00 on Monday.",
                "structured_rules": {
                    "atomic_constraints": [
                        {
                            "type": "block",
                            "days": [2],
                            "time_slot": {"start_hour": 17, "end_hour": 20},
                            "priority": "hard"
                        }
                    ]
                }
            }
        }
    )

class ConstraintSave(ConstraintBase):
    """Model used for saving the constraint confirmed by the user."""
    # This model should contain the final structured_rules as approved by the lecturer
    pass

class Constraint(ConstraintBase):
    """Full model mapping the database structure"""
    constraints_id: Optional[int] = Field(None, description="Internal ID (BIGINT, primary key)")
    last_updated_at: datetime


class SecretaryStructuredRulesEdit(BaseModel):
    """Payload for the secretary endpoint that edits a lecturer's structured rules.

    The secretary may add, edit, or delete atomic constraints, but for any
    surviving atomic the `type` (block/preference) is locked. The endpoint
    bypasses the LLM pipeline entirely; the secretary is authoritative.
    """
    structured_rules: Dict[str, Any] = Field(
        ...,
        description=(
            "Object with an 'atomic_constraints' array. Each atomic must have "
            "type ('block'|'preference'), days (unique ints in 1..6), time_slot "
            "(null for full day, or {start_hour, end_hour, start_minute?, end_minute?}), "
            "and priority ('hard'|'soft')."
        ),
    )
    raw_text: Optional[str] = Field(
        None,
        description=(
            "Optional new human-readable text for the constraint. If omitted, "
            "the server generates a preview from the rules."
        ),
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "structured_rules": {
                    "atomic_constraints": [
                        {
                            "type": "block",
                            "days": [1, 2],
                            "time_slot": {"start_hour": 8, "end_hour": 10},
                            "priority": "hard"
                        },
                        {
                            "type": "preference",
                            "days": [3],
                            "time_slot": None,
                            "priority": "soft"
                        }
                    ]
                },
                "raw_text": None
            }
        }
    )


class StructuredRulesValidationFieldError(BaseModel):
    """A single field-level validation error from StructuredRulesValidator."""
    path: str = Field(..., description="Dotted/indexed path to the offending field")
    message: str = Field(..., description="Human-readable explanation of the violation")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "path": "atomic_constraints[0].type",
                "message": "type cannot change from 'block' to 'preference'"
            }
        }
    )


class StructuredRulesValidationErrorResponse(BaseModel):
    """Wire shape returned by the secretary structured-rules edit endpoint when
    validation fails (HTTP 422)."""
    status: str = Field("error")
    errors: List[StructuredRulesValidationFieldError]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "error",
                "errors": [
                    {
                        "path": "atomic_constraints[0].type",
                        "message": "type cannot change from 'block' to 'preference'"
                    },
                    {
                        "path": "atomic_constraints[1].time_slot",
                        "message": "start_hour must be < end_hour"
                    }
                ]
            }
        }
    )


class BrokenConstraintDetail(BaseModel):
    """Details about a broken constraint"""
    constraints_id: int
    raw_text: Optional[str] = None
    lecturer_name: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "constraints_id": 88,
                "raw_text": "No teaching on Thursday.",
                "lecturer_name": "Dana Levi"
            }
        }
    )


class BrokenConstraint(SchedulaBaseModel):
    """Model for breaking_constraints table"""
    breaking_id: Optional[int] = Field(None, description="Internal ID (BIGINT, primary key)")
    constraints_id: int = Field(description="Foreign key to lecturer_constraints")
    atomic_constraint_index: int = Field(description="Index in structured_rules atomic_constraints array")
    semester_year: int = Field(..., ge=2000, le=2100, description="Semester year")
    semester_number: int = Field(..., ge=1, le=3, description="Semester number")
    is_seen: bool = Field(False, description="Whether secretary has seen this breaking constraint")
    created_at: Optional[datetime] = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "breaking_id": 12,
                "constraints_id": 88,
                "atomic_constraint_index": 0,
                "semester_year": 2026,
                "semester_number": 1,
                "is_seen": False,
                "created_at": "2026-01-12T10:00:00Z"
            }
        }
    )


class BrokenConstraintCreate(BaseModel):
    """Model for creating a new breaking constraint"""
    constraints_id: int
    atomic_constraint_index: int
    semester_year: int
    semester_number: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "constraints_id": 88,
                "atomic_constraint_index": 0,
                "semester_year": 2026,
                "semester_number": 1
            }
        }
    )


class BrokenConstraintResponse(SchedulaBaseModel):
    """Response model for breaking constraints with additional details"""
    breaking_id: int
    constraints_id: int
    atomic_constraint_index: int
    semester_year: int
    semester_number: int
    is_seen: bool
    created_at: datetime
    # Additional fields from JOIN
    raw_text: Optional[str] = None
    lecturer_name: Optional[str] = None
    lecturer_internal_id: Optional[int] = None
    atomic_constraint_detail: Optional[dict] = None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "breaking_id": 12,
                "constraints_id": 88,
                "atomic_constraint_index": 0,
                "semester_year": 2026,
                "semester_number": 1,
                "is_seen": False,
                "created_at": "2026-01-12T10:00:00Z",
                "raw_text": "No teaching on Thursday.",
                "lecturer_name": "Dana Levi",
                "lecturer_internal_id": 42,
                "atomic_constraint_detail": {
                    "type": "block",
                    "days": [5],
                    "time_slot": {"start_hour": 8, "end_hour": 20},
                    "priority": "hard"
                }
            }
        }
    )