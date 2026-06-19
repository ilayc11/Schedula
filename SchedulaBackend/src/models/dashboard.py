from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Dict
from src.models.semester import SemesterBase

class ConstraintsStats(BaseModel):
    total_lecturers: int
    submitted_count: int
    missing_count: int
    missing_lecturers: List[Dict[str, str]]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_lecturers": 30,
                "submitted_count": 24,
                "missing_count": 6,
                "missing_lecturers": [
                    {"user_name": "MShalev", "full_name": "Maya Shalev"}
                ]
            }
        }
    )

class ApprovalStats(BaseModel):
    approved: int = 0
    rejected: int = 0
    pending: int = 0

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "approved": 18,
                "rejected": 2,
                "pending": 10
            }
        }
    )

class SecretaryDashboardResponse(BaseModel):
    current_semester: SemesterBase
    constraints_stats: Optional[ConstraintsStats] = None
    approval_stats: Optional[ApprovalStats] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "current_semester": {
                    "semester_year": 2026,
                    "semester_number": 1,
                    "semester_start_date": "2026-10-15",
                    "semester_end_date": "2027-02-20",
                    "constraint_start_date": "2026-10-15",
                    "constraint_end_date": "2026-11-10",
                    "change_period_start": "2027-01-01",
                    "change_period_end": "2027-01-20",
                    "status": "SUB"
                },
                "constraints_stats": {
                    "total_lecturers": 30,
                    "submitted_count": 24,
                    "missing_count": 6,
                    "missing_lecturers": [{"user_name": "MShalev", "full_name": "Maya Shalev"}]
                },
                "approval_stats": {
                    "approved": 18,
                    "rejected": 2,
                    "pending": 10
                }
            }
        }
    )