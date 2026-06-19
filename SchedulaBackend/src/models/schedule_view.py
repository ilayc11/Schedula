# src/models/schedule_view.py (Final Updated)

from pydantic import BaseModel, Field, ConfigDict, field_serializer, field_validator
from datetime import time
from typing import Dict, Optional, List, Any
import json


class CohortInfo(BaseModel):
    """Basic cohort information for schedule views
    
    Both fields are REQUIRED (NOT NULL) to ensure precise cohort identification.
    """
    target_department_id: int = Field(..., description="Target department for this cohort (REQUIRED)")
    target_year_level: int = Field(..., ge=1, le=4, description="Target year level 1-4 (REQUIRED)")
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "target_department_id": 1,
                "target_year_level": 3
            }
        }
    )


class ScheduleSessionDetails(BaseModel):
    """
    Detailed model representing a single course session for display in the schedule view.
    Includes only the essential details for the lecturer's schedule view.
    """
    # --- Session Details ---
    session_id: int = Field(..., description="Internal PK of the session.")
    day_of_week: int = Field(..., ge=1, le=6, description="Day of week.")
    start_time: time = Field(..., description="Start time of the session.")
    end_time: time = Field(..., description="End time of the session.")

    # --- Course & Offering Details ---
    course_name: str = Field(..., description="Full name of the course .")
    course_number: int = Field(..., description="The course number.")
    offering_id: int = Field(..., description="FK to the course offering.")
    lecturer_internal_id: int = Field(..., description="FK to the lecturer user_internal_id.")
    group_number: int = Field(..., description="The group number.")
    
    # --- Cohort Details ---
    cohorts: List[CohortInfo] = Field(default_factory=list, description="Target cohorts for this offering.")

    @field_validator('cohorts', mode='before')
    @classmethod
    def parse_json_list(cls, v: Any) -> Any:
        # If the input is a string like '[]', convert it to a real list
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return []  # Default to empty list if parsing fails
        # If it's already a list or None, return as is
        return v if v is not None else []


    # --- Lecturer Details ---
    lecturer_name: str = Field(..., description="Lecturer's full name .")

    # --- Schedule & Semester Details ---
    schedule_id: int = Field(..., description="ID of the specific schedule/draft.")
    semester_year: int = Field(..., description="Semester Year.")
    semester_number: int = Field(..., description="Semester Number.")

    # --- Constraints ---
    lecturer_constraints: List[Dict[str, Any]] = Field(default_factory=list, description="List of constraints for this lecturer in this schedule.")

    # is_draft / is_published were removed as requested.

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "session_id": 901,
                "day_of_week": 2,
                "start_time": "10:00",
                "end_time": "13:00",
                "course_name": "Data Structures",
                "course_number": 20431,
                "offering_id": 120,
                "lecturer_internal_id": 42,
                "group_number": 1,
                "cohorts": [{"target_department_id": 1, "target_year_level": 3}],
                "lecturer_name": "Dana Levi",
                "schedule_id": 10,
                "semester_year": 2026,
                "semester_number": 1,
                "lecturer_constraints": [
                    {
                        "constraints_id": 123,
                        "raw_text": "I am not available on Mondays",
                        "structured_rules": {
                            "atomic_constraints": [
                                {
                                    "type": "block",
                                    "days": [2],
                                    "time_slot": {
                                        "start_hour": 0,
                                        "end_hour": 24,
                                        "start_minute": 0,
                                        "end_minute": 0,
                                    },
                                    "priority": "hard",
                                }
                            ]
                        },
                        "is_breaking": False
                    }
                ]
            }
        }
    )

    @field_serializer('start_time', 'end_time')
    def serialize_time(self, v: time) -> str:
        return v.strftime('%H:%M')
