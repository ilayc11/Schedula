# src/routes/external/lecturer/dashboard.py

from typing import List, Dict
from fastapi import APIRouter, HTTPException, status, Request
from src.repositories import semesters as semesters_repo
from src.repositories import lecturer_courses as lc_repo

router = APIRouter()


@router.get(
    "/current_semester",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Returns the current active semester with status and constraint deadline.",
            "content": {"application/json": {"example": {
                "semester_year": 2026,
                "semester_number": 1,
                "status": "SUB",
                "constraint_end_date": "2026-10-15"
            }}},
        },
        403: {
            "description": "Forbidden - User is not a Lecturer",
            "content": {"application/json": {"example": {"detail": "User does not have Lecturer privileges"}}},
        },
        404: {
            "description": "No active semester found.",
            "content": {"application/json": {"example": {"detail": "No active semester found"}}},
        },
    },
)
async def get_current_semester(
    request: Request,
):
    """
    Returns the current active semester based on date and status.
    
    Used by the frontend to determine which semester to display in the schedule view,
    along with status and constraint submission deadline.
    """
    semester = await semesters_repo.get_current_semester()
    
    if not semester:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active semester found"
        )
    
    # Convert date to string if it's a date object
    constraint_end = semester.get("constraint_end_date")
    if constraint_end is not None:
        constraint_end = str(constraint_end)
    
    return {
        "semester_year": semester["semester_year"],
        "semester_number": semester["semester_number"],
        "status": semester.get("status"),
        "constraint_end_date": constraint_end
    }


@router.get(
    "/my_courses",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Returns the courses assigned to the authenticated lecturer.",
            "content": {"application/json": {"example": [
                {
                    "course_number": 20417,
                    "course_name": "Algorithms",
                    "group_number": 1,
                    "academic_year": 2026,
                    "semester": 1,
                    "role": "Lecturer"
                }
            ]}},
        },
        403: {
            "description": "Forbidden - User is not a Lecturer",
            "content": {"application/json": {"example": {"detail": "User does not have Lecturer privileges"}}},
        },
    },
)
async def get_my_courses(
    request: Request,
) -> List[Dict[str, object]]:
    """
    Returns all courses assigned to the authenticated lecturer with course details.
    
    Used by the frontend dashboard to display the lecturer's assigned courses.
    """
    current_lecturer_id = request.state.user_internal_id
    courses = await lc_repo.list_courses_with_details_for_lecturer(current_lecturer_id)
    return courses

