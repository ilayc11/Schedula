from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from src.models.base import SchedulaBaseModel

class LecturerCourseBase(SchedulaBaseModel):
    """Base model for linking a lecturer to a course offering"""

    lecturer_internal_id: int = Field(..., description="Lecturer's internal id (FK to users.user_internal_id)")
    offering_id: int = Field(..., description="Course offering ID (FK to course_offering.offering_id)")
    role: Optional[str] = Field(None, max_length=50, description="Role of the lecturer for this offering")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "lecturer_internal_id": 42,
                "offering_id": 120,
                "role": "Lecturer"
            }
        }
    )

class LecturerCourseCreate(LecturerCourseBase):
    """Model for creating a new lecturer-course link"""
    pass

class LecturerCourseUpdate(BaseModel):
    """Model for updating lecturer-course information"""
    lecturer_internal_id: Optional[int] = Field(None)
    offering_id: Optional[int] = Field(None)
    role: Optional[str] = Field(None, max_length=50)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"role": "Coordinator"}
        }
    )

class LecturerCourseResponse(LecturerCourseBase):
    """Model for returning lecturer-course link data in responses"""
    pass

class LecturerCourse(LecturerCourseBase):
    """Full model mapping the database structure"""
    lecturer_course_id: Optional[int] = Field(..., description="Internal ID (BIGINT, primary key)")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "lecturer_course_id": 701,
                "lecturer_internal_id": 42,
                "offering_id": 120,
                "role": "Lecturer"
            }
        }
    )
