"""DEV ONLY - Fairness Reports CRUD routes"""
from typing import List, Dict
from fastapi import APIRouter, HTTPException, Body, Path

from src.repositories import fairness_reports as fr_repo
from src.models.fairness_report import FairnessReportCreate


router = APIRouter()


def clean_report_response(report: Dict[str, object]) -> Dict[str, object]:
    """Ensures internal fields are correctly named and returned."""
    return report

@router.post(
    "/",
    status_code=201,
    responses={
        201: {
            "description": "Fairness report created",
            "content": {"application/json": {"example": {"status": "INSERT 0 1"}}},
        },
        400: {
            "description": "Invalid data (e.g., non-existent FKs)",
            "content": {"application/json": {"example": {"detail": "Invalid data"}}},
        },
        422: {"description": "Validation error"},
    },
)
async def create_report(
    payload: FairnessReportCreate = Body(
        ...,
        examples=[{
            "schedule_id": 10,
            "lecturer_internal_id": 1001,
            "score": 0.87,
            "fullfilled_constraints_json": {"items": ["no_overlap", "preferred_days"]},
            "broken_constraints_json": {"items": ["max_hours_per_day"]},
        }],
    )
) -> Dict[str, object]:
    """Create a new fairness report"""
    try:
        result = await fr_repo.create_fairness_report(payload.model_dump())
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create report")
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create report: {str(e)}")


@router.get(
    "/{report_id}",
    responses={
        200: {
            "description": "Report found",
            "content": {
                "application/json": {
                    "example": {
                        "report_id": 3,
                        "schedule_id": 10,
                        "lecturer_internal_id": 1001,
                        "score": 0.87,
                        "fullfilled_constraints_json": {"items": ["no_overlap", "preferred_days"]},
                        "broken_constraints_json": {"items": ["max_hours_per_day"]},
                    }
                }
            },
        },
        404: {"description": "Report not found"},
    },
)
async def get_report(report_id: int = Path(..., description="Fairness Report Internal ID")) -> Dict[str, object]:
    """Get fairness report by ID"""
    report = await fr_repo.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail=f"Report with ID {report_id} not found")
    return clean_report_response(report)


@router.get(
    "/schedule/{schedule_id}",
    responses={
        200: {
            "description": "Reports for schedule",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "report_id": 3,
                            "schedule_id": 10,
                            "lecturer_internal_id": 1001,
                            "score": 0.87,
                            "fullfilled_constraints_json": {"items": ["no_overlap", "preferred_days"]},
                            "broken_constraints_json": {"items": ["max_hours_per_day"]},
                        }
                    ]
                }
            },
        }
    },
)
async def list_reports_for_schedule(schedule_id: int = Path(..., description="Schedule Internal ID")) -> List[Dict[str, object]]:
    """List all fairness reports for a schedule"""
    reports_list = await fr_repo.list_reports_for_schedule(schedule_id)
    return [clean_report_response(r) for r in reports_list]


@router.delete(
    "/{report_id}",
    responses={
        200: {
            "description": "Report deleted",
            "content": {"application/json": {"example": {"status": "DELETE 1"}}},
        },
        404: {"description": "Report not found"},
        400: {"description": "Deletion failed"},
    },
)
async def delete_report(report_id: int = Path(..., description="Fairness Report Internal ID")) -> Dict[str, object]:
    """Delete a fairness report"""
    try:
        # Check if report exists before attempting to delete (optional but good practice)
        if not await fr_repo.get_report(report_id):
            raise HTTPException(status_code=404, detail=f"Report with ID {report_id} not found")

        success = await fr_repo.delete_report(report_id)
        if not success:
            raise HTTPException(status_code=404, detail="Report not found or delete failed")
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to delete report: {str(e)}")