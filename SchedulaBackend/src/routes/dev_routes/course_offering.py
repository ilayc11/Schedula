"""DEV ONLY - Course Offering CRUD routes"""
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException, Body, Path, Query

from src.repositories import course_offering as co_repo

from src.models.course_offering import CourseOfferingCreate, CourseOfferingUpdate, CourseOffering


router = APIRouter()

# Helper function to exclude internal ID
def clean_offering_response(offering: Dict[str, object]) -> Dict[str, object]:
    """Ensures all fields are returned, including the internal offering_id (as required for CRUD)."""
    return offering


@router.post(
    "/",
    status_code=201,
    responses={
        201: {
            "description": "Course Offering created",
            "content": {
                "application/json": {
                    "example": {"status": "success", "offering_id": 1}
                }
            },
        },
        400: {"description": "Invalid data, e.g., unique key violation (offering already exists)"},
        422: {"description": "Validation error"},
    },
)
async def create_course_offering(
    payload: CourseOfferingCreate = Body(
        ...,
        examples=[{
            "course_number": 101,
            "academic_year": 2024,
            "semester": 1,
            "group_number": 10,
            "cohorts": [
                {"target_department_id": 1, "target_year_level": 3},
                {"target_department_id": 2, "target_year_level": 2}
            ]
        }],
    )
) -> Dict[str, object]:
    """Create a new course offering (links a course to a year/semester/group) with cohorts"""
    try:
        data = payload.model_dump(exclude={'cohorts'})
        cohorts = payload.cohorts if payload.cohorts else []
        cohort_data = [c.model_dump(exclude={'cohort_id'}) for c in cohorts] if cohorts else []
        
        result = await co_repo.create_course_offering(data, cohort_data)
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create course offering")
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create course offering: {str(e)}")


@router.get(
    "/{offering_id}",
    response_model=CourseOffering,
    responses={
        200: {
            "description": "Course Offering found by internal ID",
            "content": {
                "application/json": {
                    "example": {
                        "offering_id": 1,
                        "course_number": 101,
                        "academic_year": 2024,
                        "semester": 1,
                        "group_number": 10,
                        "cohorts": [
                            {"cohort_id": 1, "target_department_id": 1, "target_year_level": 3}
                        ]
                    }
                }
            },
        },
        404: {"description": "Course Offering not found"},
    },
)
async def get_course_offering_by_id(offering_id: int = Path(..., description="Internal Offering ID")) -> CourseOffering:
    """Get course offering by internal offering_id"""
    offering = await co_repo.get_course_offering(offering_id)
    if not offering:
        raise HTTPException(status_code=404, detail=f"Course Offering with ID {offering_id} not found")
    return clean_offering_response(offering)


@router.get(
    "/",
    response_model=List[CourseOffering],
    responses={
        200: {
            "description": "List of all course offerings",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "offering_id": 1,
                            "course_number": 101,
                            "academic_year": 2024,
                            "semester": 1,
                            "group_number": 10,
                            "cohorts": [
                                {"cohort_id": 1, "target_department_id": 1, "target_year_level": 3}
                            ]
                        }
                    ]
                }
            },
        }
    },
)
async def list_all_course_offerings() -> List[CourseOffering]:
    """List all course offerings"""
    offerings_list = await co_repo.list_course_offerings()
    return [clean_offering_response(o) for o in offerings_list]


@router.get(
    "/course/{course_number}",
    response_model=List[CourseOffering],
    responses={
        200: {"description": "List of offerings for a specific course"},
        404: {"description": "No offerings found for this course number"},
    },
)
async def list_offerings_by_course(course_number: int = Path(..., description="Course Number (FK)")) -> List[CourseOffering]:
    """List offerings for a specific course number"""
    offerings_list = await co_repo.list_course_offerings_by_course(course_number)
    if not offerings_list:
        raise HTTPException(status_code=404, detail=f"No offerings found for course {course_number}")
    return [clean_offering_response(o) for o in offerings_list]


@router.get(
    "/year/{academic_year}",
    response_model=List[CourseOffering],
    responses={
        200: {"description": "List of offerings by academic year"},
        404: {"description": "No offerings found for this year"},
    },
)
async def list_offerings_by_year(academic_year: int = Path(..., description="Academic Year (e.g., 2024)")) -> List[CourseOffering]:
    """List offerings by academic year"""
    offerings_list = await co_repo.list_course_offerings_by_year(academic_year)
    if not offerings_list:
        raise HTTPException(status_code=404, detail=f"No offerings found for year {academic_year}")
    return [clean_offering_response(o) for o in offerings_list]


@router.get(
    "/year/{academic_year}/semester/{semester}",
    response_model=List[CourseOffering],
    responses={
        200: {"description": "List of offerings for year and semester"},
        404: {"description": "No offerings found for the specified year and semester"},
    },
)
async def list_offerings_by_year_and_semester(
    academic_year: int = Path(..., description="Academic Year"),
    semester: int = Path(..., description="Semester Number (1, 2, or 3)"),
) -> List[CourseOffering]:
    """List offerings for a specific academic year and semester"""
    offerings_list = await co_repo.list_course_offerings_by_semester(academic_year, semester)
    if not offerings_list:
        raise HTTPException(status_code=404, detail=f"No offerings found for year {academic_year}, semester {semester}")
    return [clean_offering_response(o) for o in offerings_list]


@router.get(
    "/cohort/{department_id}/{year_level}/{academic_year}/{semester}",
    response_model=List[CourseOffering],
    responses={
        200: {"description": "List of offerings for a specific cohort in a semester"},
        404: {"description": "No offerings found for this cohort"},
    },
)
async def list_offerings_by_cohort(
    department_id: int = Path(..., description="Department ID"),
    year_level: int = Path(..., ge=1, le=6, description="Year Level (1-6)"),
    academic_year: int = Path(..., description="Academic Year"),
    semester: int = Path(..., description="Semester Number (1, 2, or 3)"),
) -> List[CourseOffering]:
    """List offerings for a specific cohort (department + year level) in a semester"""
    offerings_list = await co_repo.list_course_offerings_by_cohort(
        department_id, year_level, academic_year, semester
    )
    if not offerings_list:
        raise HTTPException(
            status_code=404,
            detail=f"No offerings found for department {department_id}, year {year_level} in {academic_year}/{semester}"
        )
    return [clean_offering_response(o) for o in offerings_list]


@router.get(
    "/lookup/{course_number}/{academic_year}/{semester}/{group_number}",
    response_model=CourseOffering,
    responses={
        200: {
            "description": "Specific offering found by full key",
            "content": {
                "application/json": {
                    "example": {
                        "offering_id": 1,
                        "course_number": 101,
                        "academic_year": 2024,
                        "semester": 1,
                        "group_number": 10,
                        "cohorts": [
                            {"cohort_id": 1, "target_department_id": 1, "target_year_level": 3}
                        ]
                    }
                }
            },
        },
        404: {"description": "Specific offering not found"},
    },
)
async def get_specific_offering_by_full_key(
    course_number: int = Path(..., description="Course Number"),
    academic_year: int = Path(..., description="Academic Year"),
    semester: int = Path(..., description="Semester Number"),
    group_number: int = Path(..., description="Group Number"),
) -> CourseOffering:
    """Get a specific offering using its full unique key (course/year/semester/group)"""
    offering = await co_repo.list_course_offerings_by_group(
        course_number, academic_year, semester, group_number
    )
    if not offering:
        raise HTTPException(
            status_code=404,
            detail=f"Offering not found for {course_number}/{academic_year}/{semester}/{group_number}",
        )
    return clean_offering_response(offering)


@router.patch(
    "/{offering_id}",
    responses={
        200: {
            "description": "Course Offering updated",
            "content": {"application/json": {"example": {"status": "UPDATE 1"}}},
        },
        404: {"description": "Course Offering not found"},
        400: {"description": "Invalid update data or unique key violation"},
    },
)
async def update_course_offering(offering_id: int, updates: CourseOfferingUpdate) -> Dict[str, object]:
    """Update course offering fields by offering_id"""
    try:
        # Check if offering exists first
        if not await co_repo.get_course_offering(offering_id):
            raise HTTPException(status_code=404, detail=f"Course Offering with ID {offering_id} not found")

        update_data = updates.dict(exclude_unset=True)
        if not update_data:
            return {"status": "No fields to update"}

        result = await co_repo.update_course_offering(offering_id, update_data)
        if not result:
            raise HTTPException(status_code=404, detail="Offering not found or update failed")
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update course offering: {str(e)}")


@router.delete(
    "/{offering_id}",
    responses={
        200: {
            "description": "Course Offering deleted",
            "content": {"application/json": {"example": {"status": "DELETE 1"}}},
        },
        404: {"description": "Course Offering not found"},
        400: {"description": "Deletion failed (e.g., due to foreign key constraints from course_schedules)"},
    },
)
async def delete_course_offering(offering_id: int) -> Dict[str, object]:
    """Delete a course offering by offering_id"""
    try:
        # Check if offering exists first
        if not await co_repo.get_course_offering(offering_id):
            raise HTTPException(status_code=404, detail=f"Course Offering with ID {offering_id} not found")

        result = await co_repo.delete_course_offering(offering_id)
        return {"status": result}
    except Exception as e:
        # Catch potential foreign key constraint violations
        raise HTTPException(status_code=400, detail=f"Failed to delete course offering: {str(e)}")