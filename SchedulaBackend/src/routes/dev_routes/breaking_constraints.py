"""DEV ONLY - Breaking Constraints CRUD routes"""
from typing import List, Dict, Optional, Any
from fastapi import APIRouter, HTTPException, Body, Path, Query
import json
from src.repositories import breaking_constraints as breaking_constraints_repo
from src.models.constraint import BrokenConstraintCreate, BrokenConstraint

router = APIRouter()


def clean_breaking_constraint_response(constraint: Dict[str, Any]) -> Dict[str, Any]:
    """Returns the breaking constraint object."""
    return constraint


@router.post(
    "/",
    status_code=201,
    responses={
        201: {
            "description": "Breaking constraint created",
            "content": {
                "application/json": {
                    "example": {
                        "breaking_id": 1,
                        "constraints_id": 5,
                        "atomic_constraint_index": 0,
                        "semester_year": 2025,
                        "semester_number": 1,
                        "is_seen": False,
                        "created_at": "2025-01-06T10:00:00+02:00"
                    }
                }
            },
        },
        400: {"description": "Invalid data (e.g., non-existent FKs)"},
        422: {"description": "Validation error"},
    },
)
async def create_breaking_constraint(
    payload: BrokenConstraintCreate = Body(
        ...,
        examples=[{
            "constraints_id": 5,
            "atomic_constraint_index": 0,
            "semester_year": 2025,
            "semester_number": 1,
        }],
    )
) -> Dict[str, Any]:
    """Create a new breaking constraint"""
    try:
        data = payload.model_dump()
        # Convert to list format expected by repository
        created_list = await breaking_constraints_repo.create_breaking_constraints([data])
        if not created_list:
            raise HTTPException(status_code=400, detail="Failed to create breaking constraint")
        return created_list[0]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create breaking constraint: {str(e)}")


@router.get(
    "/",
    responses={
        200: {
            "description": "List of all breaking constraints",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "count": 2,
                        "data": [
                            {
                                "breaking_id": 1,
                                "constraints_id": 5,
                                "semester_year": 2025,
                                "semester_number": 1,
                                "is_seen": False,
                                "created_at": "2025-01-06T10:00:00+02:00",
                                "lecturer_internal_id": 42,
                                "breaking_atomic_constraints": [
                                    {
                                        "atomic_constraint_index": 2,
                                        "type": "block",
                                        "days": [2],
                                        "time_slot": {"start_hour": 9, "end_hour": 12}
                                    }
                                ]
                            }
                        ]
                    }
                }
            },
        }
    },
)
async def list_all_breaking_constraints() -> Dict[str, Any]:
    """List all breaking constraints across all semesters"""
    constraints_list = await breaking_constraints_repo.list_all()
    return {
        "status": "success",
        "data": [clean_breaking_constraint_response(c) for c in constraints_list],
        "count": len(constraints_list)
    }


@router.get(
    "/{breaking_id}",
    responses={
        200: {
            "description": "Breaking constraint found",
            "content": {
                "application/json": {
                    "example": {
                        "breaking_id": 1,
                        "constraints_id": 5,
                        "semester_year": 2025,
                        "semester_number": 1,
                        "is_seen": False,
                        "lecturer_internal_id": 42,
                        "raw_text": "No classes on Wednesday mornings",
                        "breaking_atomic_constraints": [
                            {
                                "atomic_constraint_index": 0,
                                "type": "block",
                                "days": [4],
                                "time_slot": {"start_hour": 8, "end_hour": 12}
                            }
                        ]
                    }
                }
            },
        },
        404: {"description": "Breaking constraint not found"},
    },
)
async def get_breaking_constraint(
    breaking_id: int = Path(..., description="Breaking Constraint ID")
) -> Dict[str, Any]:
    """Get a specific breaking constraint by ID with details"""
    constraint = await breaking_constraints_repo.get_breaking_constraint(breaking_id)
    if not constraint:
        raise HTTPException(status_code=404, detail=f"Breaking constraint {breaking_id} not found")
    return clean_breaking_constraint_response(constraint)


@router.get(
    "/semester/{semester_year}/{semester_number}",
    responses={
        200: {
            "description": "List breaking constraints by semester (optimized structure)",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "count": 2,
                        "data": [
                            {
                                "breaking_id": 1,
                                "constraints_id": 5,
                                "semester_year": 2025,
                                "semester_number": 1,
                                "is_seen": False,
                                "created_at": "2025-01-06T10:00:00Z",
                                "lecturer_internal_id": 42,
                                "breaking_atomic_constraints": [
                                    {
                                        "atomic_constraint_index": 2,
                                        "type": "block",
                                        "days": [2],
                                        "time_slot": {"start_hour": 9, "end_hour": 12}
                                    },
                                    {
                                        "atomic_constraint_index": 4,
                                        "type": "block",
                                        "days": [4],
                                        "time_slot": {"start_hour": 14, "end_hour": 17}
                                    }
                                ]
                            }
                        ]
                    }
                }
            }
        },
        404: {"description": "No breaking constraints found for this semester"},
    },
)
async def list_by_semester(
    semester_year: int = Path(..., ge=2000, le=2100, description="Semester Year"),
    semester_number: int = Path(..., ge=1, le=3, description="Semester Number"),
    unseen_only: bool = Query(False, description="Filter to unseen constraints only"),
) -> Dict[str, Any]:
    """
    List breaking constraints for a specific semester (grouped structure).
    
    Returns grouped data (one entry per constraints_id):
    - breaking_id: Unique identifier for this breaking constraint entry
    - constraints_id: Reference to full constraint in lecturer_constraints table
    - lecturer_internal_id: Reference to lecturer (for filtering)
    - breaking_atomic_constraints: Array of breaking atomic constraints, each with:
        - atomic_constraint_index: Index in the original constraint
        - days: Array of day numbers
        - type: Constraint type (usually "block")
        - time_slot: {start_hour, end_hour}
    
    Middle ground: Compact storage (one row per constraint_id) + precise information.
    To get lecturer_name or raw_text, join with lecturer_constraints and users tables.
    """
    constraints_list = await breaking_constraints_repo.list_by_semester(
        semester_year, semester_number, unseen_only=unseen_only
    )
    if not constraints_list:
        raise HTTPException(
            status_code=404,
            detail=f"No breaking constraints found for semester {semester_year}/{semester_number}"
        )
    return {
        "status": "success",
        "data": [clean_breaking_constraint_response(c) for c in constraints_list],
        "count": len(constraints_list)
    }


@router.get(
    "/constraint/{constraints_id}",
    responses={
        200: {"description": "List breaking constraints by constraint ID"},
        404: {"description": "No breaking constraints found for this constraint"},
    },
)
async def list_by_constraint(
    constraints_id: int = Path(..., description="Lecturer Constraint ID")
) -> List[Dict[str, Any]]:
    """List all breaking instances of a specific constraint"""
    # Note: Requires adding a new repository method
    # For now, raise NotImplemented
    raise HTTPException(
        status_code=501,
        detail="Filtering by constraint_id not yet implemented. Use /semester endpoint instead."
    )


@router.patch(
    "/{breaking_id}/mark-seen",
    responses={
        200: {
            "description": "Breaking constraint marked as seen",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "data": {
                            "breaking_id": 1,
                            "constraints_id": 5,
                            "semester_year": 2025,
                            "semester_number": 1,
                            "is_seen": True,
                            "lecturer_internal_id": 42,
                            "raw_text": "No classes on Wednesday mornings",
                            "breaking_atomic_constraints": [
                                {
                                    "atomic_constraint_index": 0,
                                    "type": "block",
                                    "days": [4],
                                    "time_slot": {"start_hour": 8, "end_hour": 12}
                                }
                            ]
                        }
                    }
                }
            },
        },
        404: {"description": "Breaking constraint not found"},
    },
)
async def mark_as_seen(
    breaking_id: int = Path(..., description="Breaking Constraint ID")
) -> Dict[str, Any]:
    """Mark a breaking constraint as seen by the secretary"""
    try:
        updated = await breaking_constraints_repo.mark_as_seen(breaking_id)
        if not updated:
            raise HTTPException(status_code=404, detail=f"Breaking constraint {breaking_id} not found")
        return {"status": "success", "data": clean_breaking_constraint_response(updated)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to mark as seen: {str(e)}")


@router.patch(
    "/semester/{semester_year}/{semester_number}/mark-all-seen",
    responses={
        200: {
            "description": "All breaking constraints marked as seen",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "message": "Marked 4 breaking constraints as seen"
                    }
                }
            },
        },
        404: {"description": "No breaking constraints found"},
    },
)
async def mark_all_as_seen(
    semester_year: int = Path(..., ge=2000, le=2100, description="Semester Year"),
    semester_number: int = Path(..., ge=1, le=3, description="Semester Number"),
) -> Dict[str, Any]:
    """Mark all breaking constraints for a semester as seen"""
    try:
        count = await breaking_constraints_repo.mark_all_as_seen(semester_year, semester_number)
        if count == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No breaking constraints found for semester {semester_year}/{semester_number}"
            )
        return {
            "status": "success",
            "message": f"Marked {count} breaking constraints as seen"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to mark all as seen: {str(e)}")


@router.delete(
    "/{breaking_id}",
    responses={
        200: {
            "description": "Breaking constraint deleted",
            "content": {
                "application/json": {
                    "example": {
                        "status": "deleted"
                    }
                }
            },
        },
        404: {"description": "Breaking constraint not found"},
    },
)
async def delete_breaking_constraint(
    breaking_id: int = Path(..., description="Breaking Constraint ID")
) -> Dict[str, Any]:
    """Delete a breaking constraint by ID"""
    try:
        success = await breaking_constraints_repo.delete_breaking_constraint(breaking_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"Breaking constraint {breaking_id} not found")
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to delete breaking constraint: {str(e)}")


@router.delete(
    "/semester/{semester_year}/{semester_number}",
    responses={
        200: {
            "description": "All breaking constraints deleted for semester",
            "content": {
                "application/json": {
                    "example": {
                        "status": "deleted",
                        "message": "Cleared 4 breaking constraints for semester 2025/1"
                    }
                }
            },
        },
        404: {"description": "No breaking constraints found"},
    },
)
async def clear_by_semester(
    semester_year: int = Path(..., ge=2000, le=2100, description="Semester Year"),
    semester_number: int = Path(..., ge=1, le=3, description="Semester Number"),
) -> Dict[str, Any]:
    """Clear all breaking constraints for a specific semester"""
    try:
        count = await breaking_constraints_repo.clear_by_semester(semester_year, semester_number)
        if count == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No breaking constraints found for semester {semester_year}/{semester_number}"
            )
        return {
            "status": "deleted",
            "message": f"Cleared {count} breaking constraints for semester {semester_year}/{semester_number}"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to clear breaking constraints: {str(e)}")
