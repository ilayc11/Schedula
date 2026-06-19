import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Request, Path, Body, status, Query
from pydantic import BaseModel, ConfigDict, Field
from src.repositories import constraints as constraints_repo
from src.repositories import breaking_constraints as breaking_constraints_repo
from src.repositories import schedules as schedules_repo
from src.repositories import solver_runs as solver_runs_repo
from src.repositories import users as users_repo
from src.rabbitmq.rabbitmq import rabbitmq
from src.models.constraint import (
    SecretaryStructuredRulesEdit,
    StructuredRulesValidationErrorResponse,
)
from src.validators import (
    StructuredRulesValidationError,
    StructuredRulesValidator,
    build_preview_text,
)
from src.notifications import lecturer_events as lecturer_notifications


logger = logging.getLogger(__name__)
router = APIRouter()

REQUEST_QUEUE_NAME = "constraints_request_queue"


class ConstraintActionResponse(BaseModel):
    status: str
    message: Optional[str] = None
    data: Optional[Any] = None
    count: Optional[int] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "success",
                "message": "Constraint and all associated conflicts were deleted."
            }
        }
    )


class ConstraintPriorityUpdateRequest(BaseModel):
    secretary_override_as_hard: Optional[bool] = Field(
        default=None,
        description="Set to True for HARD override, False for SOFT override, null to use atomic priority",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "secretary_override_as_hard": True
            }
        }
    )


# --- Helpers ---
def verify_secretary(request: Request):
    if request.state.user_role != "S":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Secretary role required."
        )


# --- Update (Hard/Soft) and Delete ---

@router.patch("/{constraints_id}/priority", status_code=status.HTTP_200_OK, response_model=ConstraintActionResponse)
async def update_constraint_priority(
        request: Request,
        constraints_id: int = Path(..., description="The ID of the constraint"),
        payload: ConstraintPriorityUpdateRequest | bool | None = Body(default=None)
) -> ConstraintActionResponse:
    """
    Update a constraint priority override.
    - True: Force all atomic constraints to be HARD (cannot be relaxed)
    - False: Force all atomic constraints to be SOFT (can be relaxed)
    - null: Use per-atomic constraint priority from LLM classification

    Backward compatibility during deprecation window:
    - Accepts wrapped object body: {"secretary_override_as_hard": true|false|null}
    - Accepts legacy raw boolean body: true|false
    - Accepts null/no body as "clear override" (equivalent to null)
    """
    verify_secretary(request)

    override_value: Optional[bool]
    if isinstance(payload, ConstraintPriorityUpdateRequest):
        override_value = payload.secretary_override_as_hard
    elif isinstance(payload, bool):
        logger.warning(
            "Deprecated payload shape for update_constraint_priority on constraint %s: raw boolean body; "
            "use object wrapper with secretary_override_as_hard",
            constraints_id,
        )
        override_value = payload
    else:
        override_value = None

    try:
        updated = await constraints_repo.update_constraint(
            constraints_id,
            {"secretary_override_as_hard": override_value}
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Constraint not found")

        lecturer_internal_id = updated.get("lecturer_internal_id")
        semester_year = updated.get("semester_year")
        semester_number = updated.get("semester_number")
        if lecturer_internal_id and semester_year and semester_number:
            await lecturer_notifications.publish_constraint_edited_by_secretary(
                constraint_id=int(constraints_id),
                lecturer_internal_id=int(lecturer_internal_id),
                semester_year=int(semester_year),
                semester_number=int(semester_number),
            )

        return {"status": "success", "data": updated}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating priority: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update constraint priority")


@router.put(
    "/{constraints_id}/structured-rules",
    status_code=status.HTTP_200_OK,
    response_model=ConstraintActionResponse,
    summary="Edit a lecturer's structured rules (Secretary)",
    description=(
        "Replace the structured_rules of an existing lecturer constraint with a "
        "secretary-authored version. Bypasses the LLM pipeline. Validation enforces "
        "that the atomic 'type' (block/preference) of any surviving atomic is unchanged, "
        "days are unique ints in 1..6, time slots have start < end with hours in 0..23 "
        "(end_hour up to 24) and minutes in 0..59, and priority is 'hard' or 'soft'. "
        "The constraint is then marked is_manually_edited=true, original_raw_text is "
        "preserved (only the first edit captures it), and breaking-constraint rows are "
        "recomputed for this constraint."
    ),
    responses={
        200: {"description": "Updated constraint with edit metadata"},
        403: {"description": "Caller is not a Secretary"},
        404: {"description": "Constraint not found"},
        422: {
            "description": "Validation failed (contract violation or malformed rules)",
            "model": StructuredRulesValidationErrorResponse,
        },
    },
)
async def edit_structured_rules(
        request: Request,
        constraints_id: int = Path(..., description="The ID of the constraint to edit"),
        payload: SecretaryStructuredRulesEdit = Body(...),
) -> ConstraintActionResponse:
    """
    Secretary edits a lecturer's structured rules.

    The secretary may add, edit, or delete atomic constraints. For any
    surviving atomic the `type` (block/preference) is locked. The constraint
    is flagged `is_manually_edited=true` and the original raw text is
    preserved on the first edit so the lecturer can see what the secretary
    changed.
    """
    verify_secretary(request)

    existing = await constraints_repo.get_constraint(constraints_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Constraint not found")

    try:
        StructuredRulesValidator.validate(
            old_rules=existing.get("structured_rules"),
            new_rules=payload.structured_rules,
        )
    except StructuredRulesValidationError as ve:
        # Custom 422 with field-level errors
        raise HTTPException(status_code=422, detail=ve.to_payload())

    # Preserve the original lecturer text the FIRST time this constraint is
    # edited. Subsequent edits do not overwrite the captured original.
    captured_original = existing.get("original_raw_text") or existing.get("raw_text")

    new_raw_text = payload.raw_text or build_preview_text(payload.structured_rules)

    try:
        updated = await constraints_repo.mark_as_manually_edited(
            constraints_id=constraints_id,
            original_raw_text=captured_original,
            new_structured_rules=payload.structured_rules,
            new_raw_text=new_raw_text,
        )
        if not updated:
            raise HTTPException(status_code=500, detail="Edit operation failed")

        # Recompute breaking rows tied to this constraint. Best-effort:
        # never block the edit response on a recompute failure.
        try:
            await breaking_constraints_repo.recompute_for_constraint(constraints_id)
        except Exception as recompute_err:  # pragma: no cover - defensive
            logger.warning(
                "Failed to recompute breaking constraints for %s: %s",
                constraints_id,
                recompute_err,
            )

        # Auto-trigger a solver re-run so the schedule, breaking_constraints,
        # and fairness all converge to the new rules. Best-effort: the edit
        # has already committed, so we only warn on failure here. Multiple
        # rapid edits in the same semester are coalesced by the solver's
        # built-in batching window.
        semester_year = updated.get("semester_year") or existing.get("semester_year")
        semester_number = updated.get("semester_number") or existing.get("semester_number")
        try:
            schedule_id = existing.get("schedule_id")
            if schedule_id is None and semester_year and semester_number:
                latest = await schedules_repo.get_latest_schedule_for_semester(
                    semester_year, semester_number
                )
                if latest is not None:
                    schedule_id = latest.get("schedule_id")

            run = None
            if semester_year and semester_number:
                run = await solver_runs_repo.create_run(semester_year, semester_number)

            await rabbitmq.publish(
                REQUEST_QUEUE_NAME,
                {
                    "semester_year": semester_year,
                    "semester_number": semester_number,
                    "run_id": run["run_id"] if run else None,
                    "schedule_id": schedule_id,
                    "trigger_type": "manual",
                    "constraints_id": constraints_id,
                },
            )
            logger.info(
                "Auto-triggered solver run for constraint %s (semester=%s/%s, "
                "run_id=%s, schedule_id=%s) after secretary edit",
                constraints_id,
                semester_year,
                semester_number,
                run["run_id"] if run else None,
                schedule_id,
            )
        except Exception as enqueue_err:
            logger.warning(
                "Failed to auto-enqueue solver run after editing constraint %s: %s",
                constraints_id,
                enqueue_err,
            )

        logger.info(
            "Secretary %s edited structured rules for constraint %s",
            getattr(request.state, "user_internal_id", "?"),
            constraints_id,
        )

        lecturer_internal_id = updated.get("lecturer_internal_id") or existing.get("lecturer_internal_id")
        if lecturer_internal_id and semester_year and semester_number:
            await lecturer_notifications.publish_constraint_edited_by_secretary(
                constraint_id=int(constraints_id),
                lecturer_internal_id=int(lecturer_internal_id),
                semester_year=int(semester_year),
                semester_number=int(semester_number),
            )

        return {"status": "success", "data": updated}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error editing structured rules: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail="Failed to edit structured rules"
        )


@router.delete("/{constraints_id}", status_code=status.HTTP_200_OK, response_model=ConstraintActionResponse)
async def delete_lecturer_constraint(
        request: Request,
        constraints_id: int = Path(...)
) -> ConstraintActionResponse:
    """
    Deletes the original lecturer constraint.
    Triggers CASCADE delete on related breaking constraints.
    """
    verify_secretary(request)

    # 1. Verify existence (Good for Audit & Accuracy)
    existing = await constraints_repo.get_constraint(constraints_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Constraint not found")

    # 2. Execute deletion
    success = await constraints_repo.delete_constraint(constraints_id)
    if not success:
        raise HTTPException(status_code=500, detail="Delete operation failed")

    # 3. Log the administrative action
    logger.info(f"Secretary {request.state.user_internal_id} deleted constraint {constraints_id}")

    return {
        "status": "success",
        "message": "Constraint and all associated conflicts were deleted."
    }

# --- Fetching Constraints ---

async def _attach_lecturer_names(data: List[Dict[str, Any]]) -> None:
    """Enrich constraint rows in-place with a 'lecturer_name' field.

    Looks up each distinct lecturer_internal_id once and sets
    'lecturer_name' to "First Last" (falling back to whichever name part
    exists). Rows whose lecturer can't be resolved get None so the frontend
    can fall back to showing the id.
    """
    distinct_ids = {
        c.get("lecturer_internal_id")
        for c in data
        if c.get("lecturer_internal_id") is not None
    }
    name_by_id: Dict[int, Optional[str]] = {}
    for lecturer_internal_id in distinct_ids:
        user = await users_repo.get_user_by_internal_id(lecturer_internal_id)
        if user:
            full_name = " ".join(
                part for part in (user.get("first_name"), user.get("last_name")) if part
            ).strip()
            name_by_id[lecturer_internal_id] = full_name or None
        else:
            name_by_id[lecturer_internal_id] = None

    for c in data:
        c["lecturer_name"] = name_by_id.get(c.get("lecturer_internal_id"))


@router.get("/search", status_code=status.HTTP_200_OK, response_model=ConstraintActionResponse)
async def get_constraints(
        request: Request,
        semester_year: int = Query(None),
        semester_number: int = Query(None),
        lecturer_id: int = Query(None)
) -> ConstraintActionResponse:
    """
    Flexible search for constraints.
    Can filter by semester, lecturer, or both. If no filters, returns all.
    """
    verify_secretary(request)
    try:
        # Case: Filter by Semester AND Lecturer
        if semester_year and semester_number and lecturer_id:
            data = await constraints_repo.list_constraints_by_semester_and_lecturer(
                semester_year, semester_number, lecturer_id
            )
        # Case: Filter by Semester only
        elif semester_year and semester_number:
            data = await constraints_repo.list_constraints_by_semester(semester_year, semester_number)
        # Case: Filter by Lecturer only
        elif lecturer_id:
            data = await constraints_repo.list_constraints_by_user(lecturer_id)
        # Case: Get all
        else:
            data = await constraints_repo.list_constraints()

        await _attach_lecturer_names(data)

        return {"status": "success", "data": data, "count": len(data)}
    except Exception as e:
        logger.error(f"Error fetching constraints: {str(e)}")
        raise HTTPException(status_code=500, detail="Error retrieving data")