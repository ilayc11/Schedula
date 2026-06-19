
from datetime import datetime, time
from typing import Any, Optional, List, Dict

from pydantic import BaseModel, Field, ConfigDict, model_validator

from src.models.base import SchedulaBaseModel


class ScheduleBase(SchedulaBaseModel):
    semester_year: int = Field(..., description="Semester Year (INTEGER FK)")
    semester_number: int = Field(..., description="Semester Number (INTEGER FK)")
    is_draft: bool = Field(True, description="Draft status (BOOLEAN, default True)")
    is_published: bool = Field(False, description="Published status (BOOLEAN, default False)")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "semester_year": 2026,
                "semester_number": 1,
                "is_draft": True,
                "is_published": False
            }
        }
    )


class ScheduleCreate(ScheduleBase):
    published_at: Optional[datetime] = Field(None, description="Timestamp if the schedule is published immediately (NULLABLE)")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "semester_year": 2026,
                "semester_number": 1,
                "is_draft": True,
                "is_published": False,
                "published_at": None
            }
        }
    )


class ScheduleUpdate(BaseModel):
    is_draft: Optional[bool] = None
    is_published: Optional[bool] = None
    published_at: Optional[datetime] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "is_draft": False,
                "is_published": True,
                "published_at": "2026-01-20T12:00:00Z"
            }
        }
    )


class ScheduleResponse(ScheduleBase):
    pass


class Schedule(ScheduleBase):
    schedule_id: int = Field(..., description="Internal Primary Key (BIGINT)")
    created_at: datetime
    last_update: datetime
    published_at: Optional[datetime] = Field(None, description="Timestamp when the schedule was published (NULLABLE)")
    
    @model_validator(mode="after")
    def validate_timestamp_order(self):
        # Ensure last_update and published_at are not before created_at
        created = self.created_at
        if created is not None:
            if self.last_update is not None and self.last_update < created:
                raise ValueError("last_update cannot be before created_at")
            if self.published_at is not None and self.published_at < created:
                raise ValueError("published_at cannot be before created_at")
        return self

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "schedule_id": 10,
                "semester_year": 2026,
                "semester_number": 1,
                "is_draft": False,
                "is_published": True,
                "created_at": "2026-01-15T08:00:00Z",
                "last_update": "2026-01-20T11:50:00Z",
                "published_at": "2026-01-20T12:00:00Z"
            }
        }
    )


class ManualSessionUpsertRequest(SchedulaBaseModel):
    offering_id: int = Field(..., description="FK to course_offering.offering_id")
    lecturer_internal_id: int = Field(..., description="FK to users.user_internal_id")
    day_of_week: int = Field(..., ge=1, le=6, description="Day of week (1=Sun ... 6=Fri)")
    start_time: time = Field(..., description="Session start time")
    end_time: time = Field(..., description="Session end time")
    breaking_constraint_ids: List[Dict[str, Any]] = Field(default_factory=list, description="List of constraint that are breaking for this manual session")

    @model_validator(mode="after")
    def validate_time_window(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")

        # Keep API validation aligned with DB check constraints.
        if self.day_of_week == 6 and self.end_time > time(14, 0):
            raise ValueError("Friday sessions must end by 14:00")

        if self.day_of_week in {1, 2, 3, 4, 5} and self.end_time > time(20, 0):
            raise ValueError("Sessions on Sunday-Thursday must end by 20:00")

        return self

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "offering_id": 120,
                "lecturer_internal_id": 42,
                "day_of_week": 3,
                "start_time": "10:00:00",
                "end_time": "13:00:00",
                "breaking_constraint": [
                    {
                        "constraint_id": 55,
                        "semester_year": 2026,
                        "semester_number": 1,
                        "breaking_atomic_constraints": [{
                            "atomic_constraint_index": 0,
                            "days": [3],
                            "type": "block",
                            "time_slot": { "start_hour": 10, "end_hour": 13 }
                        }]
                    },
                ],
            }
        },
    )
