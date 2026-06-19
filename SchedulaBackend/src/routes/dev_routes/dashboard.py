from typing import Dict
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict
from src.repositories import semesters as semesters_repo

router = APIRouter()


class CurrentSemesterResponse(BaseModel):
    semester_year: int
    semester_number: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"semester_year": 2026, "semester_number": 1}
        }
    )

@router.get(
    "/current_semester",
    status_code=status.HTTP_200_OK,
    response_model=CurrentSemesterResponse,
)
async def get_current_semester_dev() -> CurrentSemesterResponse:
    """
    DEV: Returns the current active semester based on date and status.
    """
    semester = await semesters_repo.get_current_semester()
    
    if not semester:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active semester found"
        )
    
    return {
        "semester_year": semester["semester_year"],
        "semester_number": semester["semester_number"]
    }
