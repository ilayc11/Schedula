# src/routes/secretary/semester.py

from typing import List, Dict, Any, Optional
import logging
from fastapi import APIRouter, HTTPException, Body, status, Path, Query, Request
from src.notifications.period_events import process_semester_update_transition
from src.repositories import semesters as semesters_repo
from src.models.semester import SemesterCreate, SemesterUpdate, Semester as SemesterModel
from pydantic import BaseModel, Field

router = APIRouter()
logger = logging.getLogger(__name__)


# # --- Pydantic model for Path/Query parameters ---
# class SemesterKey(BaseModel):
#     semester_year: int
#     semester_number: int


@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "description": "Semester created and returned",
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
            "description": "Invalid data or semester already exists",
            "content": {"application/json": {"example": {"detail": "Semester 2026/1 already exists."}}},
        },
        403: {
            "description": "Forbidden - User is not a Secretary",
            "content": {"application/json": {"example": {"detail": "User does not have Secretary privileges"}}},
        },
    },
)
async def create_semester(
        request: Request,
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
        ),
) -> SemesterModel:
    """Create a new semester record with all necessary dates."""

    try:
        created_data = await semesters_repo.create_semester(payload.model_dump())
        if not created_data:
            # Should only happen if DB fails to return the object after insertion
            raise HTTPException(status_code=500, detail="Failed to retrieve created semester data.")

        return SemesterModel(**created_data)
    except Exception as e:
        # Assuming DB uniqueness constraints or other errors are caught here
        raise HTTPException(status_code=400, detail=str(e))


@router.put(
    "/{semester_year}/{semester_number}",
    status_code=status.HTTP_200_OK,
    response_model=SemesterModel,  # Returns the full updated model
    responses={
        200: {
            "description": "Semester updated successfully and returned.",
            "content": {"application/json": {"example": {
                "semester_year": 2026,
                "semester_number": 1,
                # ... all other fields
                "status": "PUB",
            }}},
        },
        400: {
            "description": "Invalid data or no fields provided",
            "content": {"application/json": {"example": {"detail": "No fields provided for update."}}},
        },
        404: {
            "description": "Semester not found",
            "content": {"application/json": {"example": {"detail": "Semester 2026/1 not found."}}},
        },
        403: {
            "description": "Forbidden - User is not a Secretary",
            "content": {"application/json": {"example": {"detail": "User does not have Secretary privileges"}}},
        },
    },
)
async def update_semester(
        request: Request,
        semester_year: int = Path(..., description="The year of the semester to update."),
        semester_number: int = Path(..., description="The number of the semester to update."),
        payload: SemesterUpdate = Body(
            ...,
            examples=[{"status": "PUB", "change_period_end": "2026-11-01"}],
        ),
) -> SemesterModel:
    """Update existing semester dates or status and return the updated object."""

    existing_data = await semesters_repo.get_semester(semester_year, semester_number)
    if not existing_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Semester {semester_year}/{semester_number} not found.")

    updates = payload.model_dump(exclude_unset=True)
    if 'status' in updates and updates['status'] is not None:
        updates['status'] = updates['status'].value

    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided for update.")

    try:
        updated_data = await semesters_repo.update_and_get_semester(
            semester_year,
            semester_number,
            updates
        )

        if not updated_data:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"Semester {semester_year}/{semester_number} not found.")

        try:
            await process_semester_update_transition(existing_data, updated_data)
        except Exception as notify_exc:
            logger.error(
                "Failed processing semester transition notifications for %s/%s: %s",
                semester_year,
                semester_number,
                notify_exc,
                exc_info=True,
            )

        return SemesterModel(**updated_data)
    except Exception as e:
        # Catch DB constraint violations or other errors
        raise HTTPException(status_code=400, detail=str(e))



@router.get(
    "/{semester_year}/{semester_number}",
    status_code=status.HTTP_200_OK,
    response_model=SemesterModel,
    responses={
        200: {
            "description": "Semester details returned",
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
        403: {
            "description": "Forbidden - User is not a Secretary",
            "content": {"application/json": {"example": {"detail": "User does not have Secretary privileges"}}},
        },
        404: {
            "description": "Semester not found",
            "content": {"application/json": {"example": {"detail": "Semester 2026/1 not found."}}},
        },
    },
)
async def get_specific_semester(
        request: Request,
        semester_year: int = Path(..., description="The year of the semester."),
        semester_number: int = Path(..., description="The number of the semester."),
) -> SemesterModel:
    """Retrieve details for a specific semester by year and number."""

    semester_data = await semesters_repo.get_semester(semester_year, semester_number)

    if not semester_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Semester {semester_year}/{semester_number} not found.")

    return SemesterModel(**semester_data)


@router.get(
    "/all",
    status_code=status.HTTP_200_OK,
    response_model=List[SemesterModel],
    responses={
        200: {
            "description": "List of all semesters returned, ordered newest first.",
            "content": {"application/json": {"example": [
                {
                    "semester_year": 2026,
                    "semester_number": 1,
                    # ... other fields
                    "status": "SET",
                },
                {
                    "semester_year": 2025,
                    "semester_number": 3,
                    # ... other fields
                    "status": "PUB",
                },
            ]}},
        },
        403: {
            "description": "Forbidden - User is not a Secretary",
            "content": {"application/json": {"example": {"detail": "User does not have Secretary privileges"}}},
        },
    },
)
async def list_all_semesters(
        request: Request,
) -> List[SemesterModel]:
    """Retrieve a list of all existing semesters, ordered by newest first."""

    semesters_data = await semesters_repo.list_semesters()

    if not semesters_data:
        return []

    return [SemesterModel(**data) for data in semesters_data]