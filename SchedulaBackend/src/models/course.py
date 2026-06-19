from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from src.models.base import SchedulaBaseModel


class CourseBase(SchedulaBaseModel):
    """Base course model with common fields"""

    department_id: int = Field(..., description="Department ID (INTEGER)")
    degree_level: int = Field(..., ge=1, le=10, description="Degree level (SMALLINT)")
    course_number: int = Field(..., description="Course number (INTEGER, unique)")
    course_name: str = Field(..., min_length=1, max_length=255, description="Course name (VARCHAR)")
    credit_points: Decimal = Field(..., ge=0, le=20, description="Number of credit points (NUMERIC)")
    is_scheduleable: bool = Field(
        default=True,
        description="When FALSE, the solver skips this course (e.g. research, exemption, or final-project rows).",
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "department_id": 1,
                "degree_level": 2,
                "course_number": 20431,
                "course_name": "Data Structures",
                "credit_points": 3.0,
                "is_scheduleable": True,
            }
        }
    )


class CourseCreate(CourseBase):
    """Model for creating a new course"""
    pass


class CourseUpdate(BaseModel):
    """Model for updating course information"""
    department_id: Optional[int] = Field(None)  # Fixed field name
    degree_level: Optional[int] = Field(None, ge=1, le=10)
    course_number: Optional[int] = Field(None)
    course_name: Optional[str] = Field(None, min_length=1, max_length=255)
    credit_points: Optional[Decimal] = Field(None, ge=0, le=20)
    is_scheduleable: Optional[bool] = Field(None)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "course_name": "Advanced Data Structures",
                "credit_points": 4.0
            }
        }
    )


class CourseResponse(CourseBase):
    """Model for course responses"""
    pass


class Course(CourseBase):
    """Complete course model matching database structure"""
    course_id: int = Field(..., description="Internal course ID (BIGINT)")  # Added PK

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "course_id": 17,
                "department_id": 1,
                "degree_level": 2,
                "course_number": 20431,
                "course_name": "Data Structures",
                "credit_points": 3.0,
                "is_scheduleable": True,
            }
        }
    )
