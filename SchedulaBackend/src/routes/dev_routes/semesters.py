from typing import List, Dict
from fastapi import APIRouter, HTTPException, Body

from src.repositories import semesters
from src.models.semester import SemesterCreate, Semester

router = APIRouter()


@router.post(
    "/",
    status_code=201,
    response_model=Semester,
    responses={
        201: {
            "description": "Semester created",
            "content": {"application/json": {"example": {
                "semester_year": 2026,
                "semester_number": 1,
                "semester_start_date": "2026-10-01",
                "semester_end_date": "2027-01-31",
                "constraint_start_date": "2026-09-15",
                "constraint_end_date": "2026-10-15",
                "change_period_start": "2026-10-01",
                "change_period_end": "2026-10-14",
                "status": "SET",
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
async def create_semester(
    payload: SemesterCreate = Body(
        ...,
        examples=[{
            "semester_year": 2026,
            "semester_number": 1,
            "semester_start_date": "2026-10-01",
            "semester_end_date": "2027-01-31",
            "constraint_start_date": "2026-09-15",
            "constraint_end_date": "2026-10-15",
            "change_period_start": "2026-10-01",
            "change_period_end": "2026-10-14",
            "status": "SET",
        }],
    )
) -> Semester:
    """Create a new semester"""
    try:
        # Convert enum to string for database
        data = payload.model_dump()
        if hasattr(data.get("status"), "value"):
            data["status"] = data["status"].value
        
        result = await semesters.create_semester(data)
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create semester")
        return Semester(**result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/{year}/{number}",
    responses={
        200: {
            "description": "Semester found",
            "content": {
                "application/json": {
                    "example": {
                        "semester_year": 2026,
                        "semester_number": 1,
                        "semester_start_date": "2026-10-01",
                        "semester_end_date": "2027-01-31",
                        "constraint_start_date": "2026-09-15",
                        "constraint_end_date": "2026-10-15",
                        "change_period_start": "2026-10-01",
                        "change_period_end": "2026-10-14",
                        "status": "SET",
                    }
                }
            },
        },
        404: {"description": "Semester not found"},
    },
)
async def get_semester(year: int, number: int) -> Dict[str, object]:
    """Get semester by year and number"""
    semester = await semesters.get_semester(year, number)
    if not semester:
        raise HTTPException(status_code=404, detail="Semester not found")
    return semester


@router.get(
    "/",
    responses={
        200: {
            "description": "List of semesters",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "semester_year": 2026,
                            "semester_number": 1,
                            "semester_start_date": "2026-10-01",
                            "semester_end_date": "2027-01-31",
                            "constraint_start_date": "2026-09-15",
                            "constraint_end_date": "2026-10-15",
                            "change_period_start": "2026-10-01",
                            "change_period_end": "2026-10-14",
                            "status": "SET",
                        }
                    ]
                }
            },
        }
    },
)
async def list_semesters() -> List[Dict[str, object]]:
    """List all semesters"""
    return await semesters.list_semesters()


@router.patch(
    "/{year}/{number}/status",
    responses={
        200: {
            "description": "Semester status updated",
            "content": {"application/json": {"example": {"status": "UPDATE 1"}}},
        },
        400: {"description": "Invalid status value"},
    },
)
async def update_semester_status(year: int, number: int, status: str) -> Dict[str, object]:
    """Update semester status"""
    try:
        result = await semesters.update_semester_status(year, number, status)
        if not result:
            raise HTTPException(status_code=404, detail="Semester not found or update failed")
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
