"""DEV ONLY - Schedule Approvals CRUD routes"""
from typing import List, Dict, Optional
from fastapi import APIRouter, HTTPException, Body, Path

from src.repositories import schedule_approvals as sa_repo

from src.models.schedule_approval import ScheduleApprovalCreate, ScheduleApprovalUpdate, ScheduleApproval


router = APIRouter()

# Helper function to clean response
def clean_approval_response(approval: Dict[str, object]) -> Dict[str, object]:
    """Returns the approval object, including the internal PK."""
    return approval

STATUS_DESCRIPTION = "Approval Status: PEN (Pending), APP (Approved), REJ (Rejected)"


@router.post(
    "/",
    status_code=201,
    responses={
        201: {
            "description": "Approval created or updated (upsert)",
            "content": {
                "application/json": {
                    "example": {
                        "scheapprov_id": 1,
                        "schedule_id": 1,
                        "lecturer_internal_id": 1001,
                        "status": "PEN",
                    }
                }
            },
        },
        400: {"description": "Invalid data or unique key violation"},
        422: {"description": "Validation error"},
    },
)
async def create_approval(
    payload: ScheduleApprovalCreate = Body(
        ...,
        examples=[{
            "schedule_id": 1,
            "lecturer_internal_id": 1001,
            "status": "PEN",
        }],
    )
) -> Dict[str, object]:
    """Create or update a schedule approval for a lecturer (UPSERT functionality)"""
    try:
        data = payload.model_dump()
        result = await sa_repo.create_schedule_approval_upsert(
            data["schedule_id"],
            data["lecturer_internal_id"],
            data["status"],
        )
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create/update approval")
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create/update approval: {str(e)}")


@router.get(
    "/",
    response_model=List[ScheduleApproval],
    responses={
        200: {
            "description": "List of all schedule approvals",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "scheapprov_id": 1,
                            "schedule_id": 1,
                            "lecturer_internal_id": 1001,
                            "status": "APP",
                        }
                    ]
                }
            },
        }
    },
)
async def list_all_approvals() -> List[ScheduleApproval]:
    """List all schedule approvals"""
    approvals_list = await sa_repo.list_all_approvals()
    return [clean_approval_response(a) for a in approvals_list]


@router.get(
    "/lecturer/{lecturer_internal_id}",
    response_model=List[ScheduleApproval],
    responses={
        200: {"description": "List approvals submitted by lecturer"},
        404: {"description": "No approvals found for this lecturer"},
    },
)
async def list_by_lecturer(lecturer_internal_id: int = Path(..., description="Lecturer Internal ID")) -> List[ScheduleApproval]:
    """List all schedule approvals submitted by a specific lecturer"""
    approvals_list = await sa_repo.list_approvals_by_lecturer(lecturer_internal_id)
    if not approvals_list:
        raise HTTPException(status_code=404, detail=f"No approvals found for lecturer {lecturer_internal_id}")
    return [clean_approval_response(a) for a in approvals_list]


@router.get(
    "/schedule/{schedule_id}",
    response_model=List[ScheduleApproval],
    responses={
        200: {"description": "List approvals for a specific schedule"},
        404: {"description": "No approvals found for this schedule"},
    },
)
async def list_by_schedule(schedule_id: int = Path(..., description="Schedule Internal ID")) -> List[ScheduleApproval]:
    """List all approvals related to a specific schedule"""
    approvals_list = await sa_repo.list_approvals_for_schedule(schedule_id)
    if not approvals_list:
        raise HTTPException(status_code=404, detail=f"No approvals found for schedule {schedule_id}")
    return [clean_approval_response(a) for a in approvals_list]


@router.get(
    "/schedule/{schedule_id}/lecturer/{lecturer_internal_id}",
    response_model=ScheduleApproval,
    responses={
        200: {"description": "Specific approval found"},
        404: {"description": "Approval not found"},
    },
)
async def get_specific_approval(
    schedule_id: int = Path(..., description="Schedule Internal ID"),
    lecturer_internal_id: int = Path(..., description="Lecturer Internal ID"),
) -> ScheduleApproval:
    """Get the specific approval status for a given schedule and lecturer"""
    approval = await sa_repo.get_user_approval(schedule_id, lecturer_internal_id)
    if not approval:
        raise HTTPException(
            status_code=404,
            detail=f"Approval not found for schedule {schedule_id} and lecturer {lecturer_internal_id}",
        )
    return clean_approval_response(approval)


@router.get(
    "/status/{status}",
    response_model=List[ScheduleApproval],
    responses={
        200: {"description": "List all approvals by status"},
        404: {"description": "No approvals found with this status"},
    },
)
async def list_by_status(status: str = Path(..., description=STATUS_DESCRIPTION)) -> List[ScheduleApproval]:
    """List all schedule approvals (across all schedules) by status"""
    approvals_list = await sa_repo.list_all_by_status(status.upper())
    if not approvals_list:
        raise HTTPException(status_code=404, detail=f"No approvals found with status '{status}'")
    return [clean_approval_response(a) for a in approvals_list]


@router.patch(
    "/{scheapprov_id}",
    response_model=ScheduleApproval,
    responses={
        200: {
            "description": "Approval updated",
            "content": {"application/json": {"example": {
                "scheapprov_id": 1,
                "schedule_id": 1,
                "lecturer_internal_id": 1001,
                "status": "APP",
            }}},
        },
        404: {"description": "Approval not found"},
        400: {"description": "Invalid update data"},
    },
)
async def update_approval(scheapprov_id: int, updates: ScheduleApprovalUpdate) -> ScheduleApproval:
    """Update approval fields by internal scheapprov_id (partial update)"""
    try:
        if not await sa_repo.get_approval(scheapprov_id):
            raise HTTPException(status_code=404, detail=f"Approval with ID {scheapprov_id} not found")

        update_data = updates.dict(exclude_unset=True)
        if not update_data:
            approval = await sa_repo.get_approval(scheapprov_id)
            return approval

        result = await sa_repo.update_approval(scheapprov_id, update_data)
        if not result:
            raise HTTPException(status_code=404, detail="Approval not found or update failed")
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to update approval: {str(e)}")


@router.delete(
    "/{scheapprov_id}",
    status_code=204,
    responses={
        204: {
            "description": "Approval deleted successfully",
        },
        404: {"description": "Approval not found"},
        400: {"description": "Deletion failed"},
    },
)
async def delete_approval(scheapprov_id: int) -> None:
    """Delete a schedule approval by internal scheapprov_id"""
    try:
        if not await sa_repo.get_approval(scheapprov_id):
            raise HTTPException(status_code=404, detail=f"Approval with ID {scheapprov_id} not found")

        success = await sa_repo.delete_approval(scheapprov_id)
        if not success:
            raise HTTPException(status_code=404, detail="Approval not found or delete failed")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to delete approval: {str(e)}")