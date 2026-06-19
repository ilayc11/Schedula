"""DEV ONLY - Lecturer Courses CRUD routes"""
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException, Body, Path, Query

from src.repositories import lecturer_courses as lc_repo

from src.models.lecturer_course import LecturerCourseCreate, LecturerCourseUpdate, LecturerCourse



router = APIRouter()

# Helper function to clean response
def clean_lc_response(assignment: Dict[str, object]) -> Dict[str, object]:
    """Returns the assignment, including the internal PK for subsequent PATCH/DELETE."""
    return assignment


@router.post(
    "/",
    status_code=201,
    responses={
        201: {
            "description": "Lecturer-Course link created or updated (upsert)",
            "content": {
                "application/json": {
                    "example": {"status": "INSERT 0 1"}
                }
            },
        },
        400: {"description": "Invalid data (e.g., non-existent FKs)"},
        422: {"description": "Validation error"},
    },
)
async def create_or_update_lecturer_course(
    payload: LecturerCourseCreate = Body(
        ...,
        examples=[{
            "lecturer_internal_id": 1001,
            "offering_id": 5,
            "role": "Lecturer", # e.g., Lecturer, TA, Coordinator
        }],
    )
) -> Dict[str, object]:
    """Create or update lecturer-course link (UPSERT functionality)"""
    try:
        data = payload.model_dump()
        # Use upsert function which handles both creation and update on conflict
        result = await lc_repo.create_lecturer_course_upsert(
            data["lecturer_internal_id"],
            data["offering_id"],
            data["role"]
        )
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create/update link")
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create/update link: {str(e)}")


@router.get(
    "/",
    response_model=List[LecturerCourse],
    responses={
        200: {
            "description": "List of all lecturer-course assignments",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "lecturer_course_id": 1,
                            "lecturer_internal_id": 1001,
                            "offering_id": 5,
                            "role": "Lecturer",
                        }
                    ]
                }
            },
        }
    },
)
async def list_all_assignments() -> List[LecturerCourse]:
    """List all lecturer-course assignments"""
    assignments_list = await lc_repo.list_all()
    return [clean_lc_response(a) for a in assignments_list]


@router.get(
    "/lecturer/{lecturer_internal_id}",
    response_model=List[LecturerCourse],
    responses={
        200: {"description": "List assignments by lecturer"},
        404: {"description": "No assignments found for this lecturer"},
    },
)
async def list_by_lecturer(lecturer_internal_id: int = Path(..., description="Lecturer Internal ID")) -> List[LecturerCourse]:
    """List assignments by lecturer internal ID"""
    assignments_list = await lc_repo.list_for_lecturer(lecturer_internal_id)
    if not assignments_list:
        raise HTTPException(status_code=404, detail=f"No assignments found for lecturer {lecturer_internal_id}")
    return [clean_lc_response(a) for a in assignments_list]


@router.get(
    "/offering/{offering_id}",
    response_model=List[LecturerCourse],
    responses={
        200: {"description": "List assignments by course offering"},
        404: {"description": "No assignments found for this offering"},
    },
)
async def list_by_offering(offering_id: int = Path(..., description="Course Offering ID (PK)")) -> List[LecturerCourse]:
    """List assignments by course offering ID"""
    assignments_list = await lc_repo.list_for_offering(offering_id)
    if not assignments_list:
        raise HTTPException(status_code=404, detail=f"No assignments found for offering {offering_id}")
    return [clean_lc_response(a) for a in assignments_list]


@router.get(
    "/course/{course_number}",
    response_model=List[LecturerCourse],
    responses={
        200: {"description": "List lecturers/assignments for all offerings of a course number"},
        404: {"description": "No assignments found for this course"},
    },
)
async def list_by_course(course_number: int = Path(..., description="Course Number (Public ID)")) -> List[LecturerCourse]:
    """List lecturers assigned to any offering of the given course number"""
    assignments_list = await lc_repo.list_for_course_number(course_number)
    if not assignments_list:
        raise HTTPException(status_code=404, detail=f"No assignments found for course number {course_number}")
    return [clean_lc_response(a) for a in assignments_list]


@router.get(
    "/role/{role}",
    response_model=List[LecturerCourse],
    responses={
        200: {"description": "List assignments by role"},
        404: {"description": "No assignments found for this role"},
    },
)
async def list_by_role(role: str = Path(..., description="Role (e.g., Lecturer, TA)")) -> List[LecturerCourse]:
    """List assignments by role"""
    assignments_list = await lc_repo.list_by_role(role)
    if not assignments_list:
        raise HTTPException(status_code=404, detail=f"No assignments found for role '{role}'")
    return [clean_lc_response(a) for a in assignments_list]


@router.patch(
    "/{lecturer_course_id}",
    responses={
        200: {
            "description": "Assignment updated",
            "content": {"application/json": {"example": {"status": "UPDATE 1"}}},
        },
        404: {"description": "Assignment not found"},
        400: {"description": "Invalid update data"},
    },
)
async def update_assignment(lecturer_course_id: int, updates: LecturerCourseUpdate) -> Dict[str, object]:
    """Update lecturer-course assignment by internal lecturer_course_id (partial update)"""
    try:
        # Check if link exists first
        if not await lc_repo.get_by_id(lecturer_course_id):
            raise HTTPException(status_code=404, detail=f"Assignment with ID {lecturer_course_id} not found")

        update_data = updates.dict(exclude_unset=True)
        if not update_data:
            return {"status": "No fields to update"}

        result = await lc_repo.update_lecturer_course(lecturer_course_id, update_data)
        if not result:
            raise HTTPException(status_code=404, detail="Assignment not found or update failed")
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update assignment: {str(e)}")


@router.delete(
    "/{lecturer_course_id}",
    responses={
        200: {
            "description": "Assignment deleted",
            "content": {"application/json": {"example": {"status": "DELETE 1"}}},
        },
        404: {"description": "Assignment not found"},
        400: {"description": "Deletion failed"},
    },
)
async def delete_assignment(lecturer_course_id: int) -> Dict[str, object]:
    """Delete a lecturer-course assignment by internal lecturer_course_id"""
    try:
        # Check if link exists first
        if not await lc_repo.get_by_id(lecturer_course_id):
            raise HTTPException(status_code=404, detail=f"Assignment with ID {lecturer_course_id} not found")

        result = await lc_repo.delete_lecturer_course(lecturer_course_id)
        return {"status": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to delete assignment: {str(e)}")