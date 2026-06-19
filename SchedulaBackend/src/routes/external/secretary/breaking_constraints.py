import logging
from typing import Dict, Any, List
import json

from fastapi import APIRouter, HTTPException, Request, Path, status
from pydantic import BaseModel, ConfigDict

from src.repositories import breaking_constraints as breaking_constraints_repo
from src.repositories import constraints as constraints_repo 

logger = logging.getLogger(__name__)
router = APIRouter()


class StatusCountResponse(BaseModel):
    status: str
    count: int

    model_config = ConfigDict(
        json_schema_extra={"example": {"status": "success", "count": 3}}
    )


class StatusMessageResponse(BaseModel):
    status: str
    message: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"status": "success", "message": "Breaking constraint marked as seen"}
        }
    )


class UnseenCountResponse(BaseModel):
    status: str
    data: Dict[str, int]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "success",
                "data": {"unseen_count": 2, "semester_year": 2026, "semester_number": 1}
            }
        }
    )


class StatusListResponse(BaseModel):
    status: str
    data: List[Dict[str, Any]]
    count: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "success",
                "data": [{"breaking_id": 12, "constraints_id": 88, "is_seen": False}],
                "count": 1
            }
        }
    )

def clean_breaking_constraint_response(constraint: Dict[str, Any]) -> Dict[str, Any]:
    """Returns the breaking constraint object."""
    return constraint

@router.get("/{semester_year}/{semester_number}", status_code=status.HTTP_200_OK, response_model=StatusListResponse)
async def list_breaking_constraints(
        request: Request,
        semester_year: int = Path(..., ge=2000, le=2100, description="Semester year"),
        semester_number: int = Path(..., ge=1, le=3, description="Semester number"),
        unseen_only: bool = False,
) -> StatusListResponse:
    """
    Get all breaking constraints for a specific semester (grouped structure).
    
    Breaking constraints are constraints that cannot be satisfied together
    with the existing schedule. These are identified by the solver when
    it fails to find a feasible solution.
    
    Returns grouped data (one entry per constraints_id):
    - breaking_id: Unique identifier
    - constraints_id: Reference to full constraint
    - breaking_atomic_constraints: Array of breaking atomic constraints, each with:
        - atomic_constraint_index: Index in the original constraint
        - days, type, time_slot: Constraint details
    - lecturer_internal_id: Reference to lecturer
    - raw_text: The original constraint text from lecturer_constraints
    - Metadata: semester info, is_seen flag, timestamps
    
    Middle ground: Compact storage (one row per constraint_id) + precise information.
    
    Access: Secretary only
    
    Args:
        semester_year: The year of the semester
        semester_number: The semester number (1, 2, or 3)
        unseen_only: If True, only return constraints not yet seen by secretary
    
    Returns:
        List of breaking constraints with grouped atomic constraints
    """
    # Verify user is a secretary
    user_role = request.state.user_role
    if user_role != "S":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only secretaries can view breaking constraints"
        )
    
    try:
        breaking_constraints = await breaking_constraints_repo.list_by_semester(
            semester_year, semester_number, unseen_only
        )
        
        # Repository now returns optimized structure with breaking_atomic_constraint
        # No additional enrichment needed - data is already minimal and clean
        return {
            "status": "success",
            "data": breaking_constraints,
            "count": len(breaking_constraints)
        }
        
    except Exception as e:
        logger.error(f"Error fetching breaking constraints: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch breaking constraints: {str(e)}"
        )


@router.post("/{breaking_id}/mark-seen", status_code=status.HTTP_200_OK, response_model=StatusMessageResponse)
async def mark_constraint_as_seen(
        request: Request,
        breaking_id: int = Path(..., description="Breaking constraint ID"),
) -> StatusMessageResponse:
    """
    Mark a breaking constraint as seen by the secretary.
    
    This helps track which breaking constraints have been reviewed
    and which still need attention.
    
    Access: Secretary only
    
    Args:
        breaking_id: The ID of the breaking constraint to mark as seen
    
    Returns:
        Updated breaking constraint
    """
    user_role = request.state.user_role
    if user_role != "S":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only secretaries can mark constraints as seen"
        )
    
    try:
        updated = await breaking_constraints_repo.mark_as_seen(breaking_id)
        
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Breaking constraint {breaking_id} not found"
            )
        
        logger.info(f"Breaking constraint {breaking_id} marked as seen by user {request.state.user_internal_id}")
        
        return {
            "status": "success",
            "message": "Breaking constraint marked as seen",
            "data": updated
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking constraint as seen: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark constraint as seen: {str(e)}"
        )


@router.post("/{semester_year}/{semester_number}/mark-all-seen", status_code=status.HTTP_200_OK, response_model=StatusMessageResponse)
async def mark_all_as_seen(
        request: Request,
        semester_year: int = Path(..., ge=2000, le=2100),
        semester_number: int = Path(..., ge=1, le=3),
) -> StatusMessageResponse:
    """
    Mark all breaking constraints for a semester as seen.
    
    Useful for bulk operations when secretary has reviewed all
    breaking constraints for a semester.
    
    Access: Secretary only
    """
    user_role = request.state.user_role
    if user_role != "S":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only secretaries can mark constraints as seen"
        )
    
    try:
        count = await breaking_constraints_repo.mark_all_as_seen(semester_year, semester_number)
        
        logger.info(
            f"Marked {count} breaking constraints as seen for semester {semester_year}/{semester_number} "
            f"by user {request.state.user_internal_id}"
        )
        
        return {
            "status": "success",
            "message": f"Marked {count} breaking constraints as seen",
            "count": count
        }
        
    except Exception as e:
        logger.error(f"Error marking all constraints as seen: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to mark all constraints as seen: {str(e)}"
        )


@router.get("/{semester_year}/{semester_number}/unseen-count", status_code=status.HTTP_200_OK, response_model=UnseenCountResponse)
async def get_unseen_count(
        request: Request,
        semester_year: int = Path(..., ge=2000, le=2100),
        semester_number: int = Path(..., ge=1, le=3),
) -> UnseenCountResponse:
    """
    Get count of unseen breaking constraints for a semester.
    
    Useful for displaying badges or notifications in the UI.
    
    Access: Secretary only
    """
    user_role = request.state.user_role
    if user_role != "S":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only secretaries can view breaking constraints"
        )
    
    try:
        count = await breaking_constraints_repo.get_unseen_count(semester_year, semester_number)
        
        return {
            "status": "success",
            "data": {
                "unseen_count": count,
                "semester_year": semester_year,
                "semester_number": semester_number
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting unseen count: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get unseen count: {str(e)}"
        )




@router.get(
    "/{breaking_id}",
    responses={
        200: {
            "description": "Breaking constraint found",
            "content": {
                "application/json": {
                    "example": {
                        "breaking_id": 12,
                        "constraints_id": 88,
                        "semester_year": 2026,
                        "semester_number": 1,
                        "is_seen": False,
                        "lecturer_internal_id": 42,
                        "raw_text": "No classes on Friday",
                        "breaking_atomic_constraints": [
                            {
                                "atomic_constraint_index": 0,
                                "type": "block",
                                "days": [6],
                                "time_slot": {"start_hour": 8, "end_hour": 15}
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


@router.get("/lecturer/{lecturer_id}/{semester_year}/{semester_number}", status_code=status.HTTP_200_OK, response_model=StatusListResponse)
async def list_breaking_constraints_by_lecturer(
        request: Request,
        lecturer_id: int = Path(..., description="Lecturer internal ID"),
        semester_year: int = Path(..., ge=2000, le=2100, description="Semester year"),
        semester_number: int = Path(..., ge=1, le=3, description="Semester number"),
        unseen_only: bool = False,
) -> StatusListResponse:
    """
    Get all breaking constraints for a specific lecturer in a specific semester.

    This is useful for the secretary when addressing conflicts for a specific
    person, allowing them to modify (Hard/Soft) or delete specific constraints.

    Access: Secretary only

    Responses:
        200: {
            "status": "success",
            "data": [
                {
                    "breaking_id": 15,
                    "constraints_id": 42,
                    "breaking_atomic_constraints": [
                        {
                            "atomic_constraint_index": 0,
                            "days": [1],
                            "type": "block",
                            "time_slot": {"start_hour": 8, "end_hour": 10}
                        }
                    ],
                    "semester_year": 2026,
                    "semester_number": 1,
                    "is_seen": false,
                    "lecturer_internal_id": 101,
                    "raw_text": "I cannot teach on Mondays from 8-10",
                    "created_at": "2026-01-20T10:00:00Z"
                }
            ],
            "count": 1
        }
    """
    # Authorization check
    user_role = request.state.user_role
    if user_role != "S":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only secretaries can filter breaking constraints by lecturer"
        )

    try:
        breaking_constraints = await breaking_constraints_repo.list_by_lecturer(
            semester_year, semester_number, lecturer_id
        )

        return {
            "status": "success",
            "data": breaking_constraints,
            "count": len(breaking_constraints)
        }

    except Exception as e:
        logger.error(f"Error fetching breaking constraints for lecturer {lecturer_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch breaking constraints for lecturer: {str(e)}"
        )
    

@router.get("/{semester_year}/{semester_number}/full-report", status_code=status.HTTP_200_OK)
async def get_semester_constraints_report(
        request: Request,
        semester_year: int = Path(..., ge=2000, le=2100),
        semester_number: int = Path(..., ge=1, le=3),
):
    """
    Get a comprehensive report of all constraints for a semester, enriched with breaking constraints.
    """
    user_role = request.state.user_role
    if user_role != "S":
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        all_constraints = await constraints_repo.list_constraints_by_semester(semester_year, semester_number)
        
        breaking_list = await breaking_constraints_repo.list_by_semester(semester_year, semester_number, unseen_only=False)
        
        breaking_map = {b['constraints_id']: b for b in breaking_list}

        enriched_data = []
        for conn in all_constraints:
            c_id = conn['constraints_id']
            is_broken = c_id in breaking_map
            
            enriched_item = {
                "constraints_id": c_id,
                "lecturer_id": conn['lecturer_internal_id'],
                "raw_text": conn['raw_text'],
                "structured_rules": conn.get('structured_rules'),
                "is_broken": is_broken,
                "status": "broken" if is_broken else "satisfied",
                "breaking_details": breaking_map.get(c_id) if is_broken else None,
                "is_manually_edited": bool(conn.get('is_manually_edited')),
                "original_raw_text": conn.get('original_raw_text'),
                "last_updated": conn.get('last_updated_at')
            }
            enriched_data.append(enriched_item)

        return {
            "status": "success",
            "semester_year": semester_year,
            "semester_number": semester_number,
            "data": enriched_data,
            "count": len(enriched_data)
        }

    except Exception as e:
        logger.error(f"Error generating full report: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")