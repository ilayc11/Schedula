"""DEV ONLY - Courses CRUD routes"""
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException, Body, Path, Query

from src.repositories import courses as courses_repo
# Assuming the Pydantic models are here:
from src.models.course import CourseCreate, CourseUpdate, Course



router = APIRouter()


@router.post(
    "/",
    response_model=Course,
    status_code=201,
    responses={
        201: {
            "description": "Course created",
            "content": {
                "application/json": {
                    "example": {
                        "course_number": 101,
                        "course_name": "Algorithms",
                        "department_id": 202,
                        "degree_level": 1,
                        "credit_points": 4.5,
                    }
                }
            },
        },
        400: {"description": "Invalid data, e.g., course_number already exists"},
        422: {"description": "Validation error"},
    },
)
async def create_course(
    payload: CourseCreate = Body(
        ...,
        examples=[{
            "course_number": 101,
            "course_name": "Algorithms",
            "department_id": 202,
            "degree_level": 1,
            "credit_points": 4.5,
        }],
    )
) -> Course:
    """Create a new course"""
    try:
        data = payload.model_dump()
        result = await courses_repo.create_course(data)
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create course")
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create course: {str(e)}")


@router.get(
    "/{course_number}",
    response_model=Course,
    responses={
        200: {
            "description": "Course found by number",
            "content": {
                "application/json": {
                    "example": {
                        "course_number": 101,
                        "course_name": "Algorithms",
                        "department_id": 202,
                        "degree_level": 1,
                        "credit_points": 4.5,
                    }
                }
            },
        },
        404: {"description": "Course not found"},
    },
)
async def get_course_by_number(course_number: int = Path(..., description="Course unique number")) -> Course:
    """Get course by unique course number (public identifier)"""
    course = await courses_repo.list_courses_by_number(course_number)
    if not course:
        raise HTTPException(status_code=404, detail=f"Course with number {course_number} not found")
    return clean_course_response(course)


@router.get(
    "/name/{course_name}",
    response_model=Course,
    responses={
        200: {
            "description": "Course found by name",
            "content": {
                "application/json": {
                    "example": {
                        "course_number": 101,
                        "course_name": "Algorithms 101",
                        "department_id": 5,
                        "degree_level": 1,
                        "credit_points": 4.5,
                    }
                }
            },
        },
        404: {"description": "Course not found"},
        400: {"description": "Multiple courses with the same name found (ambiguous)"},
    },
)
async def get_course_by_name(course_name: str = Path(..., description="Course name")) -> Course:
    """Get course by course name. Note: course_name is not guaranteed unique."""
    courses = await courses_repo.list_courses_by_name(course_name)
    if not courses:
        raise HTTPException(status_code=404, detail=f"Course named '{course_name}' not found")

    # In case course_name is NOT unique, we return the first one found or raise an issue.
    return clean_course_response(courses[0])


@router.get(
    "/",
    response_model=List[Course],
    responses={
        200: {
            "description": "List of all courses",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "course_number": 101,
                            "course_name": "Algorithms",
                            "department_id": 202,
                            "degree_level": 1,
                            "credit_points": 4.5,
                        }
                    ]
                }
            },
        }
    },
)
async def list_all_courses() -> List[Course]:
    """List all courses"""
    courses_list = await courses_repo.list_courses()
    return [clean_course_response(c) for c in courses_list]


@router.get(
    "/department/{department_id}",
    response_model=List[Course],
    responses={
        200: {"description": "List of courses by department"},
        404: {"description": "No courses found for this department"},
    },
)
async def list_courses_by_department(department_id: str = Path(..., description="Department ID")) -> List[Course]:
    """List courses by department ID"""
    courses_list = await courses_repo.list_courses_by_department(department_id)
    if not courses_list:
        raise HTTPException(status_code=404, detail=f"No courses found for department {department_id}")
    return [clean_course_response(c) for c in courses_list]


@router.get(
    "/degree_level/{degree_level}",
    response_model=List[Course],
    responses={
        200: {"description": "List of courses by degree level"},
        404: {"description": "No courses found for this degree level"},
    },
)
async def list_courses_by_degree_level(degree_level: int = Path(..., description="Degree Level (e.g., 1 for B.Sc)")) -> List[Course]:
    """List courses by degree level"""
    courses_list = await courses_repo.list_courses_by_degree(degree_level)
    if not courses_list:
        raise HTTPException(status_code=404, detail=f"No courses found for degree level {degree_level}")
    return [clean_course_response(c) for c in courses_list]


@router.get(
    "/credit_points/{credit_points}",
    response_model=List[Course],
    responses={
        200: {"description": "List of courses by credit points"},
        404: {"description": "No courses found with these credit points"},
    },
)
async def list_courses_by_credit_points(credit_points: float = Path(..., description="Credit points (e.g., 4.5)")) -> List[Course]:
    """List courses by credit points"""
    courses_list = await courses_repo.list_courses_by_credits(credit_points)
    if not courses_list:
        raise HTTPException(status_code=404, detail=f"No courses found with {credit_points} credit points")
    return [clean_course_response(c) for c in courses_list]


@router.patch(
    "/{course_number}",
    response_model=Course,
    responses={
        200: {
            "description": "Course updated",
            "content": {"application/json": {"example": {
                "course_number": 101,
                "course_name": "Algorithms",
                "department_id": 202,
                "degree_level": 1,
                "credit_points": 4.5,
            }}},
        },
        404: {"description": "Course not found"},
        400: {"description": "Invalid update data"},
    },
)
async def update_course(course_number: int, updates: CourseUpdate) -> Course:
    """Update course fields by course number (public identifier)"""
    try:
        course = await courses_repo.list_courses_by_number(course_number)
        if not course:
            raise HTTPException(status_code=404, detail=f"Course with number {course_number} not found")

        course_id = course["course_id"]
        update_data = updates.dict(exclude_unset=True)

        if not update_data:
            return clean_course_response(course)

        result = await courses_repo.update_course(course_id, update_data)
        if not result:
            raise HTTPException(status_code=404, detail="Course not found or update failed")
        return clean_course_response(result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update course: {str(e)}")


@router.delete(
    "/{course_number}",
    status_code=204,
    responses={
        204: {
            "description": "Course deleted successfully",
        },
        404: {"description": "Course not found"},
        400: {"description": "Deletion failed (e.g., due to foreign key constraints)"},
    },
)
async def delete_course(course_number: int) -> None:
    """Delete a course by course number (public identifier)"""
    try:
        course = await courses_repo.list_courses_by_number(course_number)
        if not course:
            raise HTTPException(status_code=404, detail=f"Course with number {course_number} not found")

        course_id = course["course_id"]
        success = await courses_repo.delete_course(course_id)
        if not success:
            raise HTTPException(status_code=404, detail="Course not found or delete failed")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to delete course: {str(e)}")