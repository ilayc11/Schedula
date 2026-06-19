import logging
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException, Body, status, Path, Request, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from src.repositories import constraints as constraints_repo
from src.repositories import solver_runs as solver_runs_repo
from src.models.constraint import (
    ConstraintPreviewPayload,
    ConstraintSavePayload,
    Constraint as ConstraintModel
)
from src.utils.llm_process import process_constraint, _get_pipeline
from src.rabbitmq.rabbitmq import rabbitmq
from src.websocket.manager import ws_manager
from src.notifications import lecturer_events as lecturer_notifications
from httpx import TimeoutException, HTTPStatusError


# Set up logging according to standards
logger = logging.getLogger(__name__)
router = APIRouter()

REQUEST_QUEUE_NAME = "constraints_request_queue"


class ConstraintPreviewResponse(BaseModel):
    status: str
    data: Dict[str, Any]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "success",
                "data": {
                    "lecturer_internal_id": 42,
                    "semester_year": 2026,
                    "semester_number": 1,
                    "raw_text": "I cannot teach on Friday.",
                    "structured_rules": {
                        "atomic_constraints": [
                            {
                                "type": "block",
                                "days": [6],
                                "time_slot": {"start_hour": 8, "end_hour": 15},
                                "priority": "hard"
                            }
                        ]
                    },
                    "has_existing": False,
                    "existing_constraint_ids": []
                }
            }
        }
    )


class ConstraintDeleteResponse(BaseModel):
    status: str
    data: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "success",
                "data": "deleted"
            }
        }
    )


class ConstraintListResponse(BaseModel):
    status: str
    data: List[ConstraintModel]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "success",
                "data": [
                    {
                        "constraints_id": 88,
                        "lecturer_internal_id": 42,
                        "schedule_id": 10,
                        "semester_year": 2026,
                        "semester_number": 1,
                        "raw_text": "No classes on Friday",
                        "structured_rules": {
                            "atomic_constraints": [
                                {
                                    "type": "block",
                                    "days": [6],
                                    "time_slot": {"start_hour": 8, "end_hour": 15},
                                    "priority": "hard"
                                }
                            ]
                        },
                        "secretary_override_as_hard": None,
                        "last_updated_at": "2026-01-12T10:00:00Z"
                    }
                ]
            }
        }
    )


def parse_json_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse JSON string fields returned by psycopg2 into Python objects.
    
    psycopg2 returns JSONB/JSON fields as strings by default.
    This function parses those strings into proper Python dicts/lists.
    
    Args:
        data: Dictionary containing potential JSON string fields
        
    Returns:
        Dictionary with parsed JSON fields
    """
    parsed = data.copy()
    
    # List of fields that might be JSON strings
    json_fields = ['cohorts', 'structured_rules', 'metadata']
    
    for field in json_fields:
        if field in parsed and isinstance(parsed[field], str):
            try:
                parsed[field] = json.loads(parsed[field])
            except (json.JSONDecodeError, TypeError):
                # If it fails to parse, leave it as is
                logger.warning(f"Failed to parse JSON field '{field}': {parsed[field]}")
                pass
    
    return parsed


@router.post("/preview", status_code=status.HTTP_200_OK, response_model=ConstraintPreviewResponse)
async def create_constraint_preview(
        request: Request,
        payload: ConstraintPreviewPayload = Body(...),
        session_id: Optional[str] = Query(None, description="WebSocket session ID for progress updates"),
) -> ConstraintPreviewResponse:
    current_lecturer_id = request.state.user_internal_id
    
    # Check if this is an edit operation via custom header
    operation_type = request.headers.get("X-Constraint-Operation", "create")
    is_edit = operation_type == "edit"
    
    # Create stage update callback if session_id is provided
    async def on_stage_update(stage: str) -> None:
        if session_id:
            await ws_manager.broadcast_stage(session_id, stage)

    print("\n" + "🚀" * 10 + " STAGE: PREVIEW START " + "🚀" * 10)
    print(f"DEBUG: User ID: {current_lecturer_id}")
    print(f"DEBUG: Operation Type: {operation_type}")
    print(f"DEBUG: WebSocket Session: {session_id}")
    print(f"DEBUG: Raw Text Received: '{payload.raw_text}'")

    pipeline = _get_pipeline()

    try:
        # STEP 1: Check for existing constraints in this semester
        all_user_constraints = await constraints_repo.list_constraints_by_user(current_lecturer_id)
        current_semester_records = [
            c for c in all_user_constraints
            if c["semester_year"] == payload.semester_year and c["semester_number"] == payload.semester_number
        ]

        final_raw_text = payload.raw_text
        has_existing = False
        
        if current_semester_records:
            has_existing = True
            
            if is_edit:
                # EDIT MODE: Don't combine, just use new text
                print(f"✏️ EDIT MODE: Found {len(current_semester_records)} existing record(s). Using new text only.")
                final_raw_text = payload.raw_text
            else:
                # CREATE MODE: Combine existing + new
                print(f"🔄 CREATE MODE: Found {len(current_semester_records)} existing records. Combining texts...")
                
                # Collect existing raw texts
                existing_raw_texts = [record["raw_text"] for record in current_semester_records]
                print(f"📝 Existing texts:")
                for i, text in enumerate(existing_raw_texts, 1):
                    print(f"   {i}. \"{text}\"")
                
                # Combine: existing (oldest first) + new (newest)
                all_texts = existing_raw_texts + [payload.raw_text]
                
                # Use TextCombinationStage to merge texts
                print("⏳ Combining constraint texts linguistically...")
                combination_result = await pipeline.text_combination_stage.process(all_texts)
                
                if not combination_result["success"]:
                    print(f"⚠️ Text combination had issues, using result anyway")
                
                final_raw_text = combination_result["combined_text"]
                print(f"✅ Combined text: \"{final_raw_text}\"")
        else:
            print("🆕 No existing constraints for this semester. Processing new constraint only.")

        # STEP 2: Process the final text (either new or combined) through pipeline
        print("⏳ Processing through full pipeline...")
        llm_response = await process_constraint(
            text=final_raw_text,
            lecturer_id=current_lecturer_id,
            semester_year=payload.semester_year,
            semester_number=payload.semester_number,
            skip_wrap_stage=is_edit,  # Skip WRAP stage if editing
            on_stage_update=on_stage_update if session_id else None
        )
        
        # Signal completion via WebSocket
        if session_id:
            await ws_manager.broadcast_complete(session_id)

        # Check Stage 0 (clarification)
        warnings = llm_response.get("result", {}).get("warnings", [])
        if warnings:
            # Check if any warning indicates clarification needed
            for warning in warnings:
                if "Clarification needed:" in warning:
                    print(f"⚠️ CLARIFICATION NEEDED: {warning}")
                    return {"status": "clarification_needed", "message": warning}

        if llm_response.get("status") != "success":
            print(f"❌ LLM FAILED: {llm_response.get('errors')}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Processing failed")

        atomic_constraints = llm_response["result"]["atomic_constraints"]
        print(f"✅ Pipeline SUCCESS: Generated {len(atomic_constraints)} atomic constraints")

        # Print atomic constraints
        for i, ac in enumerate(atomic_constraints):
            print(f"   [{i}] TEXT: {ac.get('text')}")
            print(f"       DAYS: {ac.get('days')} | PRIORITY: {ac.get('priority')}")

        structured_rules = {"atomic_constraints": atomic_constraints}
        preview_data = {
            "lecturer_internal_id": current_lecturer_id,
            "semester_year": payload.semester_year,
            "semester_number": payload.semester_number,
            "raw_text": final_raw_text,  # Combined text if CREATE, new text if EDIT
            "structured_rules": structured_rules,
            "last_updated_at": datetime.now(),
            "has_existing": has_existing,  # Flag to inform frontend
            "existing_constraint_ids": [r["constraints_id"] for r in current_semester_records]  # IDs to delete on save
        }

        print("🏁 PREVIEW FLOW FINISHED SUCCESSFULLY")
        print("=" * 40 + "\n")
        return {"status": "success", "data": preview_data}

    except Exception as e:
        print(f"💥 PREVIEW ERROR: {str(e)}")
        # Broadcast error via WebSocket if session exists
        if session_id:
            await ws_manager.broadcast_error(session_id, str(e))
        raise


@router.post("/save", status_code=status.HTTP_201_CREATED, response_model=ConstraintPreviewResponse)
async def save_confirmed_constraint(
        request: Request,
        payload: ConstraintSavePayload = Body(...),
) -> ConstraintPreviewResponse:
    """
    Save the constraint that was already processed and previewed.
    The preview endpoint handles text combination and pipeline processing.
    This endpoint just deletes old constraints and saves the new one.
    """
    current_lecturer_id = request.state.user_internal_id

    print("\n" + "💾" * 10 + " STAGE: SAVE START " + "💾" * 10)
    print(f"DEBUG: Lecturer: {current_lecturer_id} | Semester: {payload.semester_year}/{payload.semester_number}")

    try:
        new_atomics = payload.structured_rules["atomic_constraints"]
        print(f"DEBUG: Saving {len(new_atomics)} atomic constraints")

        # Fetch existing constraints for this semester (to delete them)
        all_user_constraints = await constraints_repo.list_constraints_by_user(current_lecturer_id)
        current_semester_records = [
            c for c in all_user_constraints
            if c["semester_year"] == payload.semester_year and c["semester_number"] == payload.semester_number
        ]

        # Prepare atomics for database
        simplified_atomics = []
        all_hard = True
        for atomic in new_atomics:
            prio = atomic.get("priority", "hard")
            if prio == "soft": 
                all_hard = False

            print(f"   Final DB Entry -> Days: {atomic.get('days')} | Priority: {prio}")

            simplified = {
                "type": atomic.get("type", "block"),
                "days": atomic.get("days", []),
                "time_slot": atomic.get("time_slot"),
                "priority": prio  # Preserve priority for solver (default: 'soft' if missing)
            }
            simplified_atomics.append(simplified)

        # Build final database payload
        final_db_payload = {
            "lecturer_internal_id": current_lecturer_id,
            "semester_year": payload.semester_year,
            "semester_number": payload.semester_number,
            "raw_text": payload.raw_text,  # Already combined in preview
            "structured_rules": {"atomic_constraints": simplified_atomics},
            "secretary_override_as_hard": None  # Let per-atomic priority take precedence by default
        }

        # Delete old constraints (if any)
        if current_semester_records:
            print(f"🗑️ Deleting {len(current_semester_records)} old records...")
            for record in current_semester_records:
                await constraints_repo.delete_constraint(record["constraints_id"])

        # Save the new constraint
        print("💾 Writing constraint to DB...")
        created_data = await constraints_repo.create_constraint(final_db_payload)

        new_constraint_id = created_data.get("constraints_id") if created_data else None
        if new_constraint_id is not None:
            await lecturer_notifications.publish_constraint_saved_by_lecturer(
                constraint_id=int(new_constraint_id),
                lecturer_internal_id=int(current_lecturer_id),
                semester_year=int(payload.semester_year),
                semester_number=int(payload.semester_number),
            )

        print(f"🏁 SAVE SUCCESS. Created ID: {created_data.get('constraints_id')}")
        print("=" * 40 + "\n")
        return {"status": "success", "data": created_data}

    except Exception as e:
        print(f"💥 SAVE ERROR: {str(e)}")
        raise


@router.get("/my_constraints", response_model=ConstraintListResponse)
async def get_my_constraints(request: Request) -> ConstraintListResponse:
    """Fetch all constraints for the authenticated lecturer."""
    current_lecturer_id = request.state.user_internal_id

    constraints = await constraints_repo.list_constraints_by_user(current_lecturer_id)

    # Standard format: status and data
    return {
        "status": "success",
        "data": constraints if constraints else []
    }


@router.delete("/{constraints_id}", response_model=ConstraintDeleteResponse)
async def delete_lecturer_constraint(
        request: Request,
        constraints_id: int = Path(..., description="The ID of the constraint to delete")
) -> ConstraintDeleteResponse:
    """
    Delete a specific constraint.

    This endpoint verifies that the constraint belongs to the authenticated lecturer.
    Database cascade ensures related records are also removed.
    """
    current_lecturer_id = request.state.user_internal_id

    # 1. Fetch the constraint to verify ownership
    existing_constraint = await constraints_repo.get_constraint(constraints_id)

    if not existing_constraint:
        logger.warning(f"Lecturer {current_lecturer_id} tried to delete non-existent constraint {constraints_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Constraint not found"
        )

    # 2. Security Check: Ensure the user owns this constraint
    if existing_constraint.get("lecturer_internal_id") != current_lecturer_id:
        logger.error(f"Unauthorized delete attempt: Lecturer {current_lecturer_id} on constraint {constraints_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to delete this constraint"
        )

    # 3. Perform deletion
    try:
        success = await constraints_repo.delete_constraint(constraints_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Delete operation failed"
            )

        logger.info(f"Successfully deleted constraint {constraints_id} for lecturer {current_lecturer_id}")

        return {
            "status": "success",
            "data": "deleted"
        }

    except Exception as e:
        logger.error(f"Error deleting constraint {constraints_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to delete constraint: {str(e)}"
        )