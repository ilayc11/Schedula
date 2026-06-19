from datetime import time
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, model_validator

from src.models.base import SchedulaBaseModel


class CourseScheduleBase(SchedulaBaseModel):
    """Base model for a scheduled course session"""
    offering_id: int = Field(..., description="FK to course_offering.offering_id")
    lecturer_internal_id: int = Field(description="FK to users.user_internal_id")
    schedule_id: int = Field(..., description="FK to schedules.schedule_id")
    day_of_week: int = Field(..., ge=1, le=6, description="Day of week: 1=Sun ... 6=Fri")
    start_time: time = Field(..., description="Start time of the session")
    end_time: time = Field(..., description="End time of the session")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "offering_id": 120,
                "lecturer_internal_id": 42,
                "schedule_id": 10,
                "day_of_week": 2,
                "start_time": "10:00:00",
                "end_time": "13:00:00"
            }
        }
    )

    @model_validator(mode="after")
    def validate_time_ranges(self):
        """Validate that end_time > start_time and respects daily limits"""
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")

        # Daily limits: Mon-Thu 08:00-20:00, Fri 08:00-14:00
        if self.day_of_week in range(1, 6):  # Mon-Fri
            max_end = 20 if self.day_of_week != 6 else 14
            if self.start_time < time(8, 0) or self.end_time > time(max_end, 0):
                raise ValueError(f"Session times must be between 08:00 and {max_end}:00 on day {self.day_of_week}")
        return self


class CourseScheduleCreate(CourseScheduleBase):
    """Model for creating a course schedule"""
    pass


class CourseScheduleUpdate(BaseModel):
    """Model for updating a course schedule"""
    day_of_week: Optional[int] = Field(None, ge=1, le=6)
    start_time: Optional[time] = None
    end_time: Optional[time] = None

    @model_validator(mode="after")
    def validate_time_ranges(self):
        if self.start_time and self.end_time:
            if self.end_time <= self.start_time:
                raise ValueError("end_time must be after start_time")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "day_of_week": 4,
                "start_time": "12:00:00",
                "end_time": "15:00:00"
            }
        }
    )


class CourseScheduleResponse(CourseScheduleBase):
    """Response model for returning scheduled course info"""
    pass


class CourseSchedule(CourseScheduleBase):
    """Full model mapping the database structure"""
    session_id: int = Field(..., description="Internal PK (BIGINT)")
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "session_id": 901,
                "offering_id": 120,
                "lecturer_internal_id": 42,
                "schedule_id": 10,
                "day_of_week": 2,
                "start_time": "10:00:00",
                "end_time": "13:00:00"
            }
        }
    )
