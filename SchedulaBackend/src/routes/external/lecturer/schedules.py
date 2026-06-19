# src/routes/external/lecturer/schedules.py

from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Request, Query, Body, Path
from pydantic import BaseModel, Field
from src.repositories import schedule_approvals as sa_repo
from src.repositories import semesters as semesters_repo
from src.models.schedule_approval import ScheduleApproval as ApprovalModel, ScheduleApprovalBase, \
    ApprovalStatus
from src.models.schedule_view import ScheduleSessionDetails
from src.models.semester import SemesterStatus
from src.repositories import schedule_queries as sq_repo
from src.models.solver_run import SolverStatusResponse
from src.models.constraint import BrokenConstraintDetail


router = APIRouter()


@router.get(
    "/my_schedule",
    status_code=status.HTTP_200_OK,
    response_model=List[ScheduleSessionDetails],  # Uses the updated model
    responses={
        200: {
            "description": "Returns the authenticated lecturer's detailed schedule for a specific semester.",
            "content": {"application/json": {"example": [
                {
                    "session_id": 105,
                    "schedule_id": 12,
                    "day_of_week": 2,
                    "start_time": "10:00",
                    "end_time": "12:00",
                    "course_name": "Introduction to Algorithms",
                    "course_number": 12345,
                    "lecturer_name": "Moshe Cohen",
                    "semester_year": 2026,
                    "semester_number": 1,
                    "offering_id": 50,
                    "group_number": 1,
                    "cohorts": [
                        {"target_department_id": 1, "target_year_level": 3}
                    ]
                },
            ]}},
        },
        400: {
            "description": "Missing required semester parameters.",
            "content": {"application/json": {"example": {"detail": "Semester year and number are required."}}},
        },
        403: {
            "description": "Forbidden - User is not a Lecturer or schedule viewing is not allowed during constraint submission period",
            "content": {"application/json": {"example": {"detail": "User does not have Lecturer privileges"}}},
        },
    },
)
async def get_my_detailed_schedule(
    request: Request,
    semester_year: int = Query(...),
    semester_number: int = Query(...),
    day_of_week: Optional[int] = Query(None, ge=1, le=6),
    target_department_id: Optional[int] = Query(None, description="Filter by target department"),
    target_year_level: Optional[int] = Query(None, ge=1, le=6, description="Filter by target year level"),
) -> List[ScheduleSessionDetails]:
    """
    Fetches the detailed schedule for the authenticated lecturer filtered by semester and optionally by cohort.
    """
    current_lecturer_id = request.state.user_internal_id

    # Check if semester is in constraint submission period
    semester = await semesters_repo.get_semester(semester_year, semester_number)
    if semester and (semester.get("status") == SemesterStatus.SUB.value or semester.get("status") == SemesterStatus.SET.value or semester.get("status") == SemesterStatus.REV.value):
        return []

    try:
        schedule_data = await sq_repo.get_detailed_schedule(
            lecturer_internal_id=current_lecturer_id,  # Key Filter 1
            semester_year=semester_year,  # Key Filter 2
            semester_number=semester_number,  # Key Filter 3
            day_of_week=day_of_week,  # Optional Filter
            target_department_id=target_department_id,  # Cohort Filter
            target_year_level=target_year_level  # Cohort Filter
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching schedule: {str(e)}")

    if not schedule_data:
        return []

    return [ScheduleSessionDetails(**data) for data in schedule_data]


@router.post(
    "/approval",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Schedule approval status updated successfully.",
            "content": {"application/json": {"example": {
                "message": "Thank you for the approval. You will receive an update when the final schedule is published."}}},
        },
        400: {
            "description": "Invalid data or status.",
            "content": {"application/json": {"example": {"detail": "Status must be 'APP' or 'REJ'."}}},
        },
        403: {
            "description": "Forbidden - User is not a Lecturer",
            "content": {"application/json": {"example": {"detail": "User does not have Lecturer privileges"}}},
        },
    },
)
async def submit_schedule_approval(
        request: Request,
        payload: ScheduleApprovalBase = Body(
            ...,
            examples=[{
                "schedule_id": 12,
                "status": "APP"  # Must be APP (Approved) or REJ (Rejected)
            }],
        ),
) -> Dict[str, str]:
    """
    Submits or updates the lecturer's approval status (APP/REJ) for a specific schedule.
    Uses UPSERT logic based on (schedule_id, lecturer_internal_id) to handle updates.
    """
    current_lecturer_id = request.state.user_internal_id

    # 1. Input Validation: Ensure status is APP or REJ
    if payload.status not in [ApprovalStatus.APP, ApprovalStatus.REJ]:
        raise HTTPException(status_code=400, detail="Status must be 'APP' or 'REJ'.")

    try:
        status_str = payload.status.value
        schedule_id = payload.schedule_id

        result = await sa_repo.create_schedule_approval_upsert(schedule_id, current_lecturer_id, status_str)
        
        if not result:
            raise HTTPException(status_code=500, detail="Failed to save approval")

        # 2. Determine the response message based on status
        if status_str == ApprovalStatus.APP.value:
            message = "Thank you for the approval. You will receive an update when the final schedule is published."
        else:
            message = "You have rejected the schedule. Please submit additional constraints in the constraint screen."

        return {"message": message}

    except Exception as e:
        # Catch DB errors (e.g., FK violation if schedule_id doesn't exist)
        raise HTTPException(status_code=400, detail=f"Database error during approval: {str(e)}")


@router.get(
    "/approval/{schedule_id}",
    status_code=status.HTTP_200_OK,
    response_model=ApprovalModel,
    responses={
        200: {
            "description": "Returns the lecturer's current approval status for a specific schedule.",
            "content": {"application/json": {"example": {
                "scheapprov_id": 55,
                "schedule_id": 12,
                "lecturer_internal_id": 101,
                "status": "APP"}
            }},
        },
        403: {
            "description": "Forbidden - User is not a Lecturer",
            "content": {"application/json": {"example": {"detail": "User does not have Lecturer privileges"}}},
        },
        404: {
            "description": "Approval status not found for this schedule/lecturer.",
            "content": {"application/json": {"example": {"detail": "Approval status not found."}}},
        },
    },
)
async def get_my_schedule_approval_status(
        request: Request,
        schedule_id: int = Path(..., description="The Schedule ID to check the approval status for."),
) -> ApprovalModel:
    """
    Fetches the current approval status submitted by the authenticated lecturer for a given schedule.
    """
    current_lecturer_id = request.state.user_internal_id

    approval_data = await sa_repo.get_user_approval(schedule_id, current_lecturer_id)

    if approval_data is None:
        return ApprovalModel(
            scheapprov_id=0,  
            schedule_id=schedule_id,
            lecturer_internal_id=current_lecturer_id,
            status=ApprovalStatus.PEN
        )
    
    return ApprovalModel(**approval_data)


