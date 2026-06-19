from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict

from src.models.base import SchedulaBaseModel

class OfferingCohort(SchedulaBaseModel):
    """Model for offering cohort relationship
    
    Represents a specific student cohort (department + year level) that a course offering targets.
    Both fields are REQUIRED - no NULL values allowed to ensure precise cohort definition.
    """
    cohort_id: Optional[int] = Field(None, description="Cohort ID (primary key, auto-generated)")
    offering_id: Optional[int] = Field(None, description="Offering ID (FK, set automatically)")
    target_department_id: int = Field(..., description="Target department for this cohort (REQUIRED)")
    target_year_level: int = Field(..., ge=1, le=4, description="Target year level 1-4 (REQUIRED)")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "cohort_id": 301,
                "offering_id": 120,
                "target_department_id": 1,
                "target_year_level": 3
            }
        }
    )

class CourseOfferingBase(SchedulaBaseModel):
    """Base model for course offering"""

    course_number: int = Field(..., description="Course number (FK to courses.course_number)")
    academic_year: int = Field(..., ge=2000, le=2100, description="Academic year of the offering (e.g., 2026)")
    semester: int = Field(..., ge=1, le=3, description="Semester number (1, 2, or 3)")
    group_number: int = Field(..., ge=1, description="Group number for this course offering")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "course_number": 20431,
                "academic_year": 2026,
                "semester": 1,
                "group_number": 1
            }
        }
    )

class CourseOfferingCreate(CourseOfferingBase):
    """Model for creating a new course offering with cohorts"""
    cohorts: Optional[List[OfferingCohort]] = Field(default_factory=list, description="Target cohorts for this offering")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "course_number": 20431,
                "academic_year": 2026,
                "semester": 1,
                "group_number": 1,
                "cohorts": [
                    {"target_department_id": 1, "target_year_level": 3},
                    {"target_department_id": 2, "target_year_level": 3}
                ]
            }
        }
    )

class CourseOfferingUpdate(BaseModel):
    """Model for updating an existing course offering"""
    course_number: Optional[int] = Field(None)
    academic_year: Optional[int] = Field(None, ge=2000, le=2100)
    semester: Optional[int] = Field(None, ge=1, le=3)
    group_number: Optional[int] = Field(None, ge=1)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "group_number": 2
            }
        }
    )

class CourseOfferingResponse(CourseOfferingBase):
    """Model for returning course offering data in responses"""
    offering_id: int = Field(..., description="Internal offering ID")
    cohorts: Optional[List[OfferingCohort]] = Field(default_factory=list, description="Target cohorts for this offering")

class CourseOffering(CourseOfferingBase):
    """Full model mapping the database structure"""
    offering_id: int = Field(..., description="Internal offering ID (BIGINT, primary key)")
    cohorts: Optional[List[OfferingCohort]] = Field(default_factory=list, description="Target cohorts for this offering")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "offering_id": 120,
                "course_number": 20431,
                "academic_year": 2026,
                "semester": 1,
                "group_number": 1,
                "cohorts": [
                    {"cohort_id": 301, "offering_id": 120, "target_department_id": 1, "target_year_level": 3}
                ]
            }
        }
    )
