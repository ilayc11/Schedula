"""DEV ONLY - Constraints CRUD routes"""
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException, Body, Path, Query
import json
from src.repositories import constraints as constraints_repo
from src.repositories import solver_runs as solver_runs_repo
from src.rabbitmq.rabbitmq import rabbitmq

from src.models.constraint import ConstraintCreate, ConstraintUpdate, Constraint as ConstraintModel

REQUEST_QUEUE_NAME = "constraints_request_queue"

router = APIRouter()

# Helper function to ensure consistency in response format (PK is needed for PATCH/DELETE)
def clean_constraint_response(constraint: Dict[str, object]) -> Dict[str, object]:
    """Returns the constraint object."""
    return constraint


@router.post(
    "/",
    response_model=ConstraintModel,
    status_code=201,
    responses={
        201: {
            "description": "Constraint created",
            "content": {
                "application/json": {
                    "example": {
                        "constraints_id": 1,
                        "lecturer_internal_id": 1001,
                        "schedule_id": 1,
                        "semester_year": 2024,
                        "semester_number": 1,
                        "raw_text": "אני לא פנוי בימי שני בבוקר",
                        "structured_rules": {
                            "atomic_constraints": [
                                {
                                    "type": "block",
                                    "days": [2],
                                    "time_slot": {
                                        "start_hour": 8,
                                        "end_hour": 12
                                    }
                                }
                            ]
                        },
                        "secretary_override_as_hard": None,
                        "last_updated_at": "2024-01-01T10:00:00+02:00"
                    }
                }
            },
        },
        400: {"description": "Invalid data (e.g., non-existent FKs)"},
        422: {"description": "Validation error"},
    },
)
async def create_constraint(
    payload: ConstraintCreate = Body(
        ...,
        examples=[{
            "lecturer_internal_id": 1001,
            "schedule_id": 1,
            "semester_year": 2024,
            "semester_number": 1,
            "raw_text": "אני לא פנוי בימי שני בבוקר",
            "structured_rules": {
                "atomic_constraints": [
                    {
                        "type": "block",
                        "days": [2],
                        "time_slot": {
                            "start_hour": 8,
                            "end_hour": 12
                        }
                    }
                ]
            },
            "secretary_override_as_hard": None
        }],
    )
) -> ConstraintModel:
    """Create a new constraint"""
    try:
        data = payload.model_dump()
        result = await constraints_repo.create_constraint(data)
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create constraint")

        # Create a pending solver run to track the solving process
        try:
            await solver_runs_repo.create_run(
                semester_year=result["semester_year"],
                semester_number=result["semester_number"]
            )
        except Exception as e:
            print(f"Failed to create solver run: {e}")

        # Publish to RabbitMQ to trigger the solver
        try:
            await rabbitmq.publish(REQUEST_QUEUE_NAME, {
                "semester_year": result["semester_year"],
                "semester_number": result["semester_number"],
                "new_constraint_id": result["constraints_id"],
                "lecturer_id": result["lecturer_internal_id"]
            })
        except Exception as e:
            print(f"Failed to publish to RabbitMQ: {e}")

        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create constraint: {str(e)}")


@router.get(
    "/",
    response_model=List[ConstraintModel],
    responses={
        200: {
            "description": "List of all constraints (ordered by latest update)",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "constraints_id": 1,
                            "lecturer_internal_id": 1001,
                            "schedule_id": 1,
                            "semester_year": 2024,
                            "semester_number": 1,
                            "raw_text": "אני לא פנוי בימי שני בבוקר",
                            "structured_rules": {},
                            "last_updated_at": "2024-01-01T10:00:00+02:00"
                        }
                    ]
                }
            },
        }
    },
)
async def list_all_constraints() -> List[ConstraintModel]:
    """List all constraints, ordered by most recent update"""
    constraints_list = await constraints_repo.list_constraints()
    return [clean_constraint_response(c) for c in constraints_list]


@router.get(
    "/lecturer/{lecturer_internal_id}",
    response_model=List[ConstraintModel],
    responses={
        200: {"description": "List constraints by lecturer"},
        404: {"description": "No constraints found for this lecturer"},
    },
)
async def list_by_lecturer(lecturer_internal_id: int = Path(..., description="Lecturer Internal ID")) -> List[ConstraintModel]:
    """List all constraints submitted by a specific lecturer"""
    constraints_list = await constraints_repo.list_constraints_by_user(lecturer_internal_id)
    if not constraints_list:
        raise HTTPException(status_code=404, detail=f"No constraints found for lecturer {lecturer_internal_id}")
    return [clean_constraint_response(c) for c in constraints_list]


@router.get(
    "/semester/{semester_year}/{semester_number}",
    response_model=List[ConstraintModel],
    responses={
        200: {"description": "List constraints by semester"},
        404: {"description": "No constraints found for this semester"},
    },
)
async def list_by_semester(
    semester_year: int = Path(..., description="Semester Year (e.g., 2024)"),
    semester_number: int = Path(..., description="Semester Number (1, 2, or 3)"),
) -> List[ConstraintModel]:
    """List all constraints relevant to a specific semester"""
    constraints_list = await constraints_repo.list_constraints_by_semester(semester_year, semester_number)
    if not constraints_list:
        raise HTTPException(status_code=404, detail=f"No constraints found for semester {semester_year}/{semester_number}")
    return [clean_constraint_response(c) for c in constraints_list]


@router.get(
    "/schedule/{schedule_id}",
    response_model=List[ConstraintModel],
    responses={
        200: {"description": "List constraints associated with a specific schedule"},
        404: {"description": "No constraints found for this schedule"},
    },
)
async def list_by_schedule(schedule_id: int = Path(..., description="Schedule Internal ID")) -> List[ConstraintModel]:
    """List all constraints linked to a specific schedule"""
    constraints_list = await constraints_repo.list_constraints_by_schedule(schedule_id)
    if not constraints_list:
        raise HTTPException(status_code=404, detail=f"No constraints found for schedule {schedule_id}")
    return [clean_constraint_response(c) for c in constraints_list]


@router.get(
    "/lecturer/{lecturer_internal_id}/latest",
    response_model=ConstraintModel,
    responses={
        200: {"description": "Latest constraint for lecturer found"},
        404: {"description": "No constraints found for this lecturer"},
    },
)
async def get_latest_constraint_for_lecturer(
    lecturer_internal_id: int = Path(..., description="Lecturer Internal ID")
) -> ConstraintModel:
    """Get the latest constraint (by last_updated_at) for a specific lecturer"""
    constraint = await constraints_repo.get_latest_constraint_by_lecturer(lecturer_internal_id)
    if not constraint:
        raise HTTPException(status_code=404, detail=f"No latest constraint found for lecturer {lecturer_internal_id}")
    return clean_constraint_response(constraint)


@router.patch(
    "/{constraints_id}",
    responses={
        200: {
            "description": "Constraint updated",
            "content": {"application/json": {"example": {"status": "UPDATE 1"}}},
        },
        404: {"description": "Constraint not found"},
        400: {"description": "Invalid update data"},
    },
)
async def update_constraint(constraints_id: int, updates: ConstraintUpdate) -> Dict[str, object]:
    """Update constraint fields by internal ID (partial update)"""
    try:
        if not await constraints_repo.get_constraint(constraints_id):
            raise HTTPException(status_code=404, detail=f"Constraint with ID {constraints_id} not found")

        update_data = updates.dict(exclude_unset=True)

        if not update_data:
            return {"status": "No fields to update"}

        result = await constraints_repo.update_constraint(constraints_id, update_data)
        if not result:
            raise HTTPException(status_code=404, detail="Constraint not found or update failed")
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update constraint: {str(e)}")


@router.delete(
    "/{constraints_id}",
    responses={
        200: {
            "description": "Constraint deleted",
            "content": {"application/json": {"example": {"status": "DELETE 1"}}},
        },
        404: {"description": "Constraint not found"},
        400: {"description": "Deletion failed"},
    },
)
async def delete_constraint(constraints_id: int) -> Dict[str, object]:
    """Delete a constraint by internal ID"""
    try:
        if not await constraints_repo.get_constraint(constraints_id):
            raise HTTPException(status_code=404, detail=f"Constraint with ID {constraints_id} not found")

        success = await constraints_repo.delete_constraint(constraints_id)
        if not success:
            raise HTTPException(status_code=404, detail="Constraint not found or delete failed")
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to delete constraint: {str(e)}")