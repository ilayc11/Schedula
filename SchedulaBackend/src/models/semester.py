from enum import Enum
from datetime import date
from pydantic import BaseModel, Field, ConfigDict, model_validator
from typing import Optional

from src.models.base import SchedulaBaseModel


class SemesterStatus(str, Enum):
    SET = "SET"
    SUB = "SUB"
    REV = "REV"
    CHA = "CHA"
    PUB = "PUB"

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        schema = handler(core_schema)
        schema["example"] = "SUB"
        return schema


class SemesterBase(SchedulaBaseModel):
    semester_year: int = Field(..., ge=2000, le=2100)
    semester_number: int = Field(..., ge=1, le=3)
    semester_start_date: date
    semester_end_date: date
    constraint_start_date: date
    constraint_end_date: date
    change_period_start: date
    change_period_end: date
    status: SemesterStatus

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "semester_year": 2026,
                "semester_number": 1,
                "semester_start_date": "2026-10-15",
                "semester_end_date": "2027-02-20",
                "constraint_start_date": "2026-10-15",
                "constraint_end_date": "2026-11-10",
                "change_period_start": "2027-01-01",
                "change_period_end": "2027-01-20",
                "status": "SUB"
            }
        }
    )
    
    @model_validator(mode='after')
    def validate_date_ranges(self):
        """Validate that all date ranges are logical."""
        if self.semester_end_date <= self.semester_start_date:
            raise ValueError("semester_end_date must be after semester_start_date")
        
        if self.constraint_end_date <= self.constraint_start_date:
            raise ValueError("constraint_end_date must be after constraint_start_date")
        
        if self.change_period_end <= self.change_period_start:
            raise ValueError("change_period_end must be after change_period_start")
        
        # Constraint and change periods can start before semester
        # Only validate that constraint_end_date is before or during semester_end_date
        if self.constraint_end_date > self.semester_end_date:
            raise ValueError("constraint_end_date cannot be after semester_end_date")
        
        if self.change_period_end > self.semester_end_date:
            raise ValueError("change_period_end cannot be after semester_end_date")
        
        return self


class SemesterCreate(SemesterBase):
    pass


class SemesterUpdate(BaseModel):
    semester_start_date: Optional[date] = None
    semester_end_date: Optional[date] = None
    constraint_start_date: Optional[date] = None
    constraint_end_date: Optional[date] = None
    change_period_start: Optional[date] = None
    change_period_end: Optional[date] = None
    status: Optional[SemesterStatus] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "constraint_end_date": "2026-11-15",
                "status": "REV"
            }
        }
    )


class SemesterResponse(SemesterBase):
    pass


class Semester(SemesterBase):
    pass
