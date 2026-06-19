"""DEV ONLY - Courses Schedules (Session) CRUD routes"""
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException, Body, Path, Query
from datetime import time, timedelta
from src.repositories import courses_schedules as cs_repo


from src.models.course_schedule import CourseScheduleCreate, CourseScheduleUpdate, CourseSchedule


router = APIRouter()

# Helper function to clean response
def clean_session_response(session: Dict[str, object]) -> Dict[str, object]:
    """Returns the session object, including the internal PK for subsequent PATCH/DELETE."""
    return session


@router.post(
    "/",
    status_code=201,
    responses={
        201: {
            "description": "Course Session created or updated (upsert)",
            "content": {
                "application/json": {
                    "example": {"status": "INSERT 0 1"}
                }
            },
        },
        400: {"description": "Invalid data (e.g., non-existent FKs, time range violation)"},
        422: {"description": "Validation error"},
    },
)
async def create_session(
    payload: CourseScheduleCreate = Body(
        ...,
        examples=[{
            "offering_id": 5,
            "lecturer_internal_id": 1001,
            "schedule_id": 1,
            "day_of_week": 2, # Monday
            "start_time": "10:00:00",
            "end_time": "12:00:00",
        }],
    )
) -> Dict[str, object]:
    """Create a new course session or update existing one if (offering, schedule, day, start_time) conflicts"""
    try:
        data = payload.model_dump()
        result = await cs_repo.create_course_schedule_upsert(
            data["offering_id"],
            data["lecturer_internal_id"],
            data["schedule_id"],
            data["day_of_week"],
            data["start_time"],
            data["end_time"],
        )
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create/update session")
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create/update session: {str(e)}")


@router.get(
    "/",
    response_model=List[CourseSchedule],
    responses={
        200: {
            "description": "List of all course sessions",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "session_id": 1,
                            "offering_id": 5,
                            "lecturer_internal_id": 1001,
                            "schedule_id": 1,
                            "day_of_week": 2,
                            "start_time": "10:00:00",
                            "end_time": "12:00:00",
                        }
                    ]
                }
            },
        }
    },
)
async def list_all_sessions() -> List[CourseSchedule]:
    """List all course sessions"""
    sessions_list = await cs_repo.list_sessions()
    return [clean_session_response(s) for s in sessions_list]


@router.get(
    "/offering/{offering_id}",
    response_model=List[CourseSchedule],
    responses={
        200: {"description": "List sessions by course offering"},
        404: {"description": "No sessions found for this offering"},
    },
)
async def list_by_offering(offering_id: int = Path(..., description="Course Offering ID")) -> List[CourseSchedule]:
    """List all sessions belonging to a specific course offering"""
    sessions_list = await cs_repo.list_sessions_for_offering(offering_id)
    if not sessions_list:
        raise HTTPException(status_code=404, detail=f"No sessions found for offering {offering_id}")
    return [clean_session_response(s) for s in sessions_list]


@router.get(
    "/lecturer/{lecturer_internal_id}",
    response_model=List[CourseSchedule],
    responses={
        200: {"description": "List sessions by lecturer"},
        404: {"description": "No sessions found for this lecturer"},
    },
)
async def list_by_lecturer(lecturer_internal_id: int = Path(..., description="Lecturer Internal ID")) -> List[CourseSchedule]:
    """List all sessions assigned to a specific lecturer"""
    sessions_list = await cs_repo.list_sessions_for_lecturer(lecturer_internal_id)
    if not sessions_list:
        raise HTTPException(status_code=404, detail=f"No sessions found for lecturer {lecturer_internal_id}")
    return [clean_session_response(s) for s in sessions_list]


@router.get(
    "/schedule/{schedule_id}",
    response_model=List[CourseSchedule],
    responses={
        200: {"description": "List sessions by schedule"},
        404: {"description": "No sessions found for this schedule"},
    },
)
async def list_by_schedule(schedule_id: int = Path(..., description="Schedule Internal ID")) -> List[CourseSchedule]:
    """List all sessions included in a specific schedule"""
    sessions_list = await cs_repo.list_sessions_for_schedule(schedule_id)
    if not sessions_list:
        raise HTTPException(status_code=404, detail=f"No sessions found for schedule {schedule_id}")
    return [clean_session_response(s) for s in sessions_list]


@router.get(
    "/day/{day_of_week}",
    response_model=List[CourseSchedule],
    responses={
        200: {"description": "List sessions by day of week"},
        404: {"description": "No sessions found for this day"},
    },
)
async def list_by_day(day_of_week: int = Path(..., description="Day of Week (1=Sun, 6=Fri)")) -> List[CourseSchedule]:
    """List all sessions on a specific day of the week"""
    sessions_list = await cs_repo.list_sessions_by_day(day_of_week)
    if not sessions_list:
        raise HTTPException(status_code=404, detail=f"No sessions found for day {day_of_week}")
    return [clean_session_response(s) for s in sessions_list]


@router.get(
    "/start_time/{start_time}",
    response_model=List[CourseSchedule],
    responses={
        200: {"description": "List sessions by start time"},
        404: {"description": "No sessions found starting at this time"},
    },
)
async def list_by_start_time(start_time: str = Path(..., description="Start Time (HH:MM:SS)")) -> List[CourseSchedule]:
    """List all sessions starting at a specific time"""
    sessions_list = await cs_repo.list_sessions_by_start_time(start_time)
    if not sessions_list:
        raise HTTPException(status_code=404, detail=f"No sessions found starting at {start_time}")
    return [clean_session_response(s) for s in sessions_list]


@router.get(
    "/end_time/{end_time}",
    response_model=List[CourseSchedule],
    responses={
        200: {"description": "List sessions by end time"},
        404: {"description": "No sessions found ending at this time"},
    },
)
async def list_by_end_time(end_time: str = Path(..., description="End Time (HH:MM:SS)")) -> List[CourseSchedule]:
    """List all sessions ending at a specific time"""
    sessions_list = await cs_repo.list_sessions_by_end_time(end_time)
    if not sessions_list:
        raise HTTPException(status_code=404, detail=f"No sessions found ending at {end_time}")
    return [clean_session_response(s) for s in sessions_list]


@router.patch(
    "/{session_id}",
    responses={
        200: {
            "description": "Session updated",
            "content": {"application/json": {"example": {"status": "UPDATE 1"}}},
        },
        404: {"description": "Session not found"},
        400: {"description": "Invalid update data (e.g., unique key violation)"},
    },
)
async def update_session(session_id: int, updates: CourseScheduleUpdate) -> Dict[str, str]:
    """Update course session fields by internal session_id (partial update)"""
    try:
        if not await cs_repo.get_session(session_id):
            raise HTTPException(status_code=404, detail=f"Session with ID {session_id} not found")

        update_data = updates.dict(exclude_unset=True)
        if not update_data:
            return {"status": "No fields to update"}

        result = await cs_repo.update_session(session_id, update_data)
        if not result:
            raise HTTPException(status_code=404, detail="Session not found or update failed")
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update session: {str(e)}")


@router.delete(
    "/{session_id}",
    responses={
        200: {
            "description": "Session deleted",
            "content": {"application/json": {"example": {"status": "DELETE 1"}}},
        },
        404: {"description": "Session not found"},
        400: {"description": "Deletion failed"},
    },
)
async def delete_session(session_id: int) -> Dict[str, str]:
    """Delete a course session by internal session_id"""
    try:
        if not await cs_repo.get_session(session_id):
            raise HTTPException(status_code=404, detail=f"Session with ID {session_id} not found")

        success = await cs_repo.delete_session(session_id)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found or delete failed")
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to delete session: {str(e)}")