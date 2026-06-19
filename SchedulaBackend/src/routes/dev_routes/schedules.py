"""DEV ONLY - Schedules CRUD routes"""
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException, Body, Query
from src.repositories import schedules
from src.repositories import schedule_queries as sq_repo
from src.models.schedule import ScheduleCreate
from src.models.schedule_view import ScheduleSessionDetails

router = APIRouter()


@router.get(
    "/my_schedule",
    response_model=List[ScheduleSessionDetails],
    responses={
        200: {
            "description": "Returns the detailed schedule for a specific lecturer (DEV MODE).",
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
    },
)
async def get_my_detailed_schedule_dev(
    semester_year: int = Query(...),
    semester_number: int = Query(...),
    lecturer_id: int = Query(..., description="The internal ID of the lecturer (DEV ONLY)"),
    day_of_week: Optional[int] = Query(None, ge=1, le=6),
    target_department_id: Optional[int] = Query(None, description="Filter by target department"),
    target_year_level: Optional[int] = Query(None, ge=1, le=6, description="Filter by target year level"),
) -> List[ScheduleSessionDetails]:
    """
    DEV: Fetches the detailed schedule for a specific lecturer filtered by semester and optionally by cohort.
    Allows passing lecturer_id manually.
    """
    try:
        schedule_data = await sq_repo.get_detailed_schedule(
            lecturer_internal_id=lecturer_id,
            semester_year=semester_year,
            semester_number=semester_number,
            day_of_week=day_of_week,
            target_department_id=target_department_id,
            target_year_level=target_year_level
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching schedule: {str(e)}")

    if not schedule_data:
        return []

    return [ScheduleSessionDetails(**data) for data in schedule_data]


@router.post(
    "/",
    status_code=201,
    responses={
        201: {
            "description": "Schedule created",
            "content": {"application/json": {"example": {
                "schedule_id": 10,
                "semester_year": 2026,
                "semester_number": 1,
                "is_draft": True,
                "is_published": False,
                "created_at": "2025-11-29T12:00:00Z",
                "last_update": "2025-11-29T12:00:00Z",
                "published_at": None,
            }}},
        },
        400: {
            "description": "Invalid data",
            "content": {"application/json": {"example": {"detail": "Invalid data"}}},
        },
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {"type": "missing", "loc": ["body", "semester_year"], "msg": "Field required", "input": None}
                        ]
                    }
                }
            },
        },
    },
)
async def create_schedule(
    payload: ScheduleCreate = Body(
        ...,
        examples=[{
            "semester_year": 2026,
            "semester_number": 1,
            "is_draft": True,
            "is_published": False,
        }],
    )
) -> Dict[str, object]:
    """Create a new schedule"""
    try:
        result = await schedules.create_schedule(payload.model_dump())
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create schedule")
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/",
    responses={
        200: {
            "description": "List all schedules",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "schedule_id": 10,
                            "semester_year": 2026,
                            "semester_number": 1,
                            "is_draft": True,
                            "is_published": False,
                            "created_at": "2025-11-29T12:00:00Z",
                            "last_update": "2025-11-29T12:00:00Z",
                            "published_at": None,
                        }
                    ]
                }
            },
        }
    },
)
async def list_all_schedules() -> List[Dict[str, object]]:
    """List all schedules"""
    return await schedules.list_all_schedules()


@router.get(
    "/{schedule_id}",
    responses={
        200: {
            "description": "Schedule found",
            "content": {
                "application/json": {
                    "example": {
                        "schedule_id": 10,
                        "semester_year": 2026,
                        "semester_number": 1,
                        "is_draft": True,
                        "is_published": False,
                        "created_at": "2025-11-29T12:00:00Z",
                        "last_update": "2025-11-29T12:00:00Z",
                        "published_at": None,
                    }
                }
            },
        },
        404: {"description": "Schedule not found"},
    },
)
async def get_schedule(schedule_id: int) -> Dict[str, object]:
    """Get schedule by ID"""
    schedule = await schedules.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return schedule


@router.get(
    "/semester/{year}/{number}",
    responses={
        200: {
            "description": "Schedules in semester",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "schedule_id": 10,
                            "semester_year": 2026,
                            "semester_number": 1,
                            "is_draft": True,
                            "is_published": False,
                            "created_at": "2025-11-29T12:00:00Z",
                            "last_update": "2025-11-29T12:00:00Z",
                            "published_at": None,
                        }
                    ]
                }
            },
        }
    },
)
async def list_by_semester(year: int, number: int) -> List[Dict[str, object]]:
    """List schedules for a specific semester"""
    return await schedules.list_by_semester(year, number)


@router.patch(
    "/{schedule_id}",
    responses={
        200: {
            "description": "Schedule updated",
            "content": {"application/json": {"example": {
                "schedule_id": 10,
                "semester_year": 2026,
                "semester_number": 1,
                "is_draft": True,
                "is_published": False,
                "created_at": "2025-11-29T12:00:00Z",
                "last_update": "2025-11-29T12:00:00Z",
                "published_at": None,
            }}},
        },
        400: {"description": "Invalid update data"},
    },
)
async def update_schedule(
    schedule_id: int,
    updates: Dict[str, object] = Body(
        ...,
        example={
            "is_draft": False,
            "is_published": True,
            "published_at": "2026-01-20T12:00:00Z"
        },
    ),
) -> Dict[str, object]:
    """Update schedule fields"""
    try:
        result = await schedules.update_schedule(schedule_id, updates)
        if not result:
            raise HTTPException(status_code=404, detail="Schedule not found")
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/{schedule_id}",
    status_code=204,
    responses={
        204: {
            "description": "Schedule deleted successfully",
        }
    },
)
async def delete_schedule(schedule_id: int) -> None:
    """Delete a schedule"""
    try:
        success = await schedules.delete_schedule(schedule_id)
        if not success:
            raise HTTPException(status_code=404, detail="Schedule not found or delete failed")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
