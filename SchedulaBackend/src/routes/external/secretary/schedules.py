# src/routes/secretary/schedules.py

import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Body, status, Path, Query, Request
from fastapi.responses import Response

from src.models.constraint import BrokenConstraintDetail
from src.models.solver_run import SolverStatusResponse
from src.repositories import schedules as schedules_repo
from src.models.schedule import (
    ScheduleCreate,
    ScheduleUpdate,
    Schedule as ScheduleModel,
    ManualSessionUpsertRequest,
)
from src.repositories import schedule_queries as sq_repo
from src.models.schedule_view import ScheduleSessionDetails
from src.repositories import solver_runs as solver_runs_repo
from src.routes.external.lecturer.constraints import parse_json_fields
from src.repositories import constraints as constraints_repo
from src.repositories import breaking_constraints as breaking_constraints_repo
from src.rabbitmq.rabbitmq import rabbitmq
from src.notifications import lecturer_events as lecturer_notifications
from src.utils import schedule_export

logger = logging.getLogger(__name__)
router = APIRouter()

REQUEST_QUEUE_NAME = "constraints_request_queue"


@router.post(
    "/publish_request",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ScheduleModel,
    responses={
        202: {
            "description": "Schedule created and CSP solver request published to RabbitMQ queue.",
            "content": {"application/json": {"example": {
                "schedule_id": 15,
                "semester_year": 2027, "semester_number": 1,
                "is_draft": True, "is_published": False,
                "created_at": "2026-10-01T10:00:00",
                "last_update": "2026-10-01T10:00:00",
                "published_at": None
            }}},
        },
        400: {
            "description": "Invalid data or semester not found.",
            "content": {"application/json": {"example": {"detail": "Semester 2027/1 not found."}}},
        },
        403: {
            "description": "Forbidden - User is not a Secretary",
            "content": {"application/json": {"example": {"detail": "User does not have Secretary privileges"}}},
        },
    },
)
async def create_schedule_and_trigger_csp(
        request: Request,
        payload: ScheduleCreate = Body(
            ...,
            examples=[{"semester_year": 2027, "semester_number": 1, "is_draft": True, "is_published": False}],
        ),
) -> ScheduleModel:
    """
    Creates a new schedule record, then sends a request to RabbitMQ to trigger the CSP solver.
    """

    try:
        # Reuse an existing empty draft (one whose courses_schedules is empty,
        # e.g., from a previous failed/not-yet-completed run) before inserting
        # a new schedule row. This keeps the schedule_id we return to the
        # caller stable across retries and prevents empty drafts from piling
        # up on every trigger.
        existing_empty = await schedules_repo.find_empty_draft_for_semester(
            payload.semester_year, payload.semester_number
        )
        if existing_empty is not None:
            created_data = existing_empty
            logger.info(
                "publish_request: reusing empty draft schedule_id=%s for %s/%s",
                existing_empty["schedule_id"],
                payload.semester_year,
                payload.semester_number,
            )
        else:
            created_data = await schedules_repo.create_schedule(payload.model_dump())

        if not created_data:
            raise HTTPException(status_code=500, detail="Failed to create schedule record.")

        schedule_id = created_data.get("schedule_id")
        
        # Create a solver run record
        run = await solver_runs_repo.create_run(
            payload.semester_year,
            payload.semester_number
        )
        
        if not run:
            logger.error(
                f"Failed to create solver run record for {payload.semester_year}/{payload.semester_number}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create solver run record"
            )
        
        # Publish request to RabbitMQ to trigger solver
        await rabbitmq.publish(REQUEST_QUEUE_NAME, {
            "semester_year": payload.semester_year,
            "semester_number": payload.semester_number,
            "run_id": run["run_id"],
            "schedule_id": schedule_id,
            "trigger_type": "manual"
        })
        
        logger.info(
            f"Solver triggered for semester {payload.semester_year}/{payload.semester_number}, "
            f"schedule_id={schedule_id}, run_id={run['run_id']}"
        )

        return ScheduleModel(**created_data)

    except Exception as e:
        logger.error(f"Error creating schedule and triggering solver: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))



@router.get(
    "/{schedule_id}/status",
    status_code=status.HTTP_200_OK,
    response_model=ScheduleModel,
    responses={
        200: {
            "description": "Returns the status and metadata of the schedule.",
            "content": {"application/json": {"example": {
                "schedule_id": 15,
                "semester_year": 2027, "semester_number": 1,
                "is_draft": True, "is_published": False,
                "created_at": "2026-10-01T10:00:00",
                "last_update": "2026-10-01T11:30:00",
                "published_at": None
            }}},
        },
        403: {
            "description": "Forbidden - User is not a Secretary",
            "content": {"application/json": {"example": {"detail": "User does not have Secretary privileges"}}},
        },
        404: {
            "description": "Schedule not found",
            "content": {"application/json": {"example": {"detail": "Schedule ID 15 not found."}}},
        },
    },
)
async def get_schedule_status(
        request: Request,
        schedule_id: int = Path(..., description="The ID of the schedule to check."),
) -> ScheduleModel:
    """Retrieve the current status (draft/published, timestamps) of a specific schedule."""

    schedule_data = await schedules_repo.get_schedule(schedule_id)

    if not schedule_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Schedule ID {schedule_id} not found.")

    return ScheduleModel(**schedule_data)



@router.put(
    "/{schedule_id}",
    status_code=status.HTTP_200_OK,
    response_model=ScheduleModel,
    responses={
        200: {
            "description": "Schedule metadata updated successfully.",
            "content": {"application/json": {"example": {
                "schedule_id": 15,
                "is_draft": False, "is_published": True,
                "published_at": "2026-10-01T12:00:00",
                "last_update": "2026-10-01T12:00:00",
                "semester_year": 2027, "semester_number": 1,
            }}},
        },
        400: {
            "description": "Invalid data or no fields provided.",
            "content": {
                "application/json": {"example": {"detail": "Cannot set is_published=True if published_at is None."}}},
        },
        404: {
            "description": "Schedule not found",
            "content": {"application/json": {"example": {"detail": "Schedule ID 15 not found."}}},
        },
    },
)
async def update_schedule_metadata(
        request: Request,
        schedule_id: int = Path(..., description="The ID of the schedule to update."),
        payload: ScheduleUpdate = Body(
            ...,
            examples=[{"is_draft": False, "is_published": True, "published_at": "2026-10-01T12:00:00"}],
        ),
) -> ScheduleModel:
    """Update metadata fields (is_draft, is_published, published_at) of a schedule."""

    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields provided for update.")

    try:

        # Capture the existing publish state so we can detect a FALSE -> TRUE
        # transition on is_published after the update succeeds. This guard is
        # the only idempotency mechanism for the schedule_published event:
        # repeated PUTs with is_published=True won't republish.
        existing = await schedules_repo.get_schedule(schedule_id)
        previously_published = bool(existing.get("is_published")) if existing else False

        result = await schedules_repo.update_schedule(schedule_id, updates)

        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Schedule ID {schedule_id} not found.")

        updated_data = await schedules_repo.get_schedule(schedule_id)

        if not updated_data:
            raise HTTPException(status_code=500, detail="Failed to retrieve updated schedule data.")

        if not previously_published and bool(updated_data.get("is_published")):
            await lecturer_notifications.publish_schedule_published(
                schedule_id=int(schedule_id),
                semester_year=int(updated_data["semester_year"]),
                semester_number=int(updated_data["semester_number"]),
            )

        return ScheduleModel(**updated_data)

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))



@router.get(
    "/{schedule_id}/details",
    status_code=status.HTTP_200_OK,
    response_model=List[ScheduleSessionDetails],
    responses={
        200: {
            "description": "Returns the detailed schedule sessions for the given Schedule ID.",
            "content": {"application/json": {"example": [
                {
                    "session_id": 105,
                    "schedule_id": 12,
                    "day_of_week": 2,
                    "start_time": "10:00",
                    "end_time": "12:00",
                    "course_name": "Introduction to Algorithms",
                    "course_number": 12345,
                    "lecturer_name": "Moshe Cohen",
                    "semester_year": 2026,
                    "semester_number": 1,
                    "lecturer_internal_id": 101,
                    "offering_id": 50,
                    "group_number": 1,
                    "lecturer_constraints": [
                        {
                            "constraints_id": 123,
                            "raw_text": "I am not available on Mondays",
                            "structured_rules": {
                                "atomic_constraints": [
                                    {
                                        "type": "block",
                                        "days": [2],
                                        "time_slot": {
                                            "start_hour": 0,
                                            "end_hour": 24,
                                            "start_minute": 0,
                                            "end_minute": 0,
                                        },
                                        "priority": "hard",
                                    }
                                ]
                            },
                            "is_breaking": False
                        }
                    ]
                }
            ]}},
        },
        404: {
            "description": "Schedule not found or no sessions found for this schedule.",
            "content": {"application/json": {"example": {"detail": "Schedule ID 12 not found."}}},
        },
        403: {
            "description": "Forbidden - User is not a Secretary",
            "content": {"application/json": {"example": {"detail": "User does not have Secretary privileges"}}},
        },
    },
)
async def get_detailed_schedule_view(
    request: Request,
    schedule_id: int = Path(..., description="The ID of the schedule to retrieve details for."),
    day_of_week: Optional[int] = Query(None, ge=1, le=6, description="Optional filter by day of week."),
    lecturer_name: Optional[str] = Query(None, description="Optional filter by lecturer's full or partial name (e.g., 'Cohen')."), # 🆕 NEW
    group_number: Optional[int] = Query(None, description="Optional filter by course group number."), # 🆕 NEW
) -> List[ScheduleSessionDetails]:
    """
    Fetches all detailed, scheduled sessions for a given schedule ID (Secretary View).
    """

    try:
        schedule_data = await sq_repo.get_detailed_schedule(
            schedule_id=schedule_id,
            day_of_week=day_of_week,
            lecturer_name_filter=lecturer_name,

            group_number_filter=group_number
        )
        parsed_data = [parse_json_fields(data) for data in schedule_data]

        # Fetch constraints for this schedule
        constraints = await constraints_repo.list_constraints_by_schedule(schedule_id)
        
        # Fetch breaking constraints for this schedule
        breaking_constraints = await breaking_constraints_repo.list_by_schedule(schedule_id)
        breaking_constraints_ids = {bc['constraints_id'] for bc in breaking_constraints}
        
        # Group constraints by lecturer_internal_id
        constraints_by_lecturer = {}
        for constraint in constraints:
            lecturer_id = constraint['lecturer_internal_id']
            if lecturer_id not in constraints_by_lecturer:
                constraints_by_lecturer[lecturer_id] = []
            # Add is_breaking flag
            constraint['is_breaking'] = constraint['constraints_id'] in breaking_constraints_ids
            constraints_by_lecturer[lecturer_id].append(constraint)
        
        # Add constraints to each session data
        for data in parsed_data:
            lecturer_id = data['lecturer_internal_id']
            data['lecturer_constraints'] = constraints_by_lecturer.get(lecturer_id, [])

        return [ScheduleSessionDetails(**data) for data in parsed_data]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error fetching schedule details: {str(e)}")


@router.get(
    "/{schedule_id}/export",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Schedule assignments exported as a downloadable CSV or PDF file.",
            "content": {
                "text/csv": {},
                "application/pdf": {},
            },
        },
        400: {"description": "Invalid export format requested."},
        404: {"description": "Schedule not found or has no assignments."},
        403: {"description": "Forbidden - User is not a Secretary"},
    },
)
async def export_schedule_assignments(
    request: Request,
    schedule_id: int = Path(..., description="The ID of the schedule to export."),
    format: str = Query("csv", description="Export format: 'csv' or 'pdf'."),
    day_of_week: Optional[int] = Query(None, ge=1, le=6, description="Optional filter by day of week."),
    lecturer_name: Optional[str] = Query(None, description="Optional filter by lecturer name (partial/full)."),
    group_number: Optional[int] = Query(None, description="Optional filter by course group number."),
) -> Response:
    """
    Export all assignments of a schedule as a CSV or PDF file.

    The same optional filters as the details view are supported so the export
    reflects whatever the secretary is currently looking at. Returns the file
    as a binary download with the appropriate Content-Disposition header.
    """
    export_format = (format or "csv").lower()
    if export_format not in ("csv", "pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid format. Use 'csv' or 'pdf'.",
        )

    # Confirm the schedule exists so we can 404 (rather than silently exporting
    # an empty file for a bad id) and build a meaningful title/filename.
    schedule = await schedules_repo.get_schedule(schedule_id)
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Schedule ID {schedule_id} not found.",
        )

    try:
        sessions = await sq_repo.get_detailed_schedule(
            schedule_id=schedule_id,
            day_of_week=day_of_week,
            lecturer_name_filter=lecturer_name,
            group_number_filter=group_number,
        )
        sessions = [parse_json_fields(s) for s in sessions]
    except Exception as e:
        logger.error(f"Error fetching schedule {schedule_id} for export: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Error preparing export: {str(e)}")

    title = (
        f"Schedule Assignments - {schedule.get('semester_year')}/"
        f"{schedule.get('semester_number')} (Schedule {schedule_id})"
    )
    base_filename = f"schedule_{schedule_id}_assignments"

    if export_format == "csv":
        content = schedule_export.build_csv(sessions)
        media_type = "text/csv; charset=utf-8"
        filename = f"{base_filename}.csv"
    else:
        content = schedule_export.build_pdf(sessions, title=title)
        media_type = "application/pdf"
        filename = f"{base_filename}.pdf"

    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=content, media_type=media_type, headers=headers)


@router.get(
    "/{schedule_id}/offerings-distribution",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Offerings split into scheduled and unscheduled buckets.",
            "content": {
                "application/json": {
                    "example": {
                        "scheduled": [
                            {
                                "offering_id": 120,
                                "course_number": 20431,
                                "course_name": "Data Structures",
                                "group_number": 1,
                                "cohorts": [{"target_department_id": 1, "target_year_level": 3}],
                                "session_details": {
                                    "session_id": 901,
                                    "day_of_week": 3,
                                    "start_time": "10:00:00",
                                    "end_time": "13:00:00"
                                }
                            }
                        ],
                        "unscheduled": [
                            {
                                "offering_id": 121,
                                "course_number": 20432,
                                "course_name": "Algorithms",
                                "group_number": 2,
                                "cohorts": [{"target_department_id": 2, "target_year_level": 2}],
                                "session_details": None
                            }
                        ],
                        "total_count": 2,
                        "scheduled_count": 1,
                        "unscheduled_count": 1
                    }
                }
            },
        }
    },
)
async def get_all_semester_offerings(
        request: Request,
        schedule_id: int = Path(..., description="The ID of the schedule to analyze"),
        semester_year: int = Query(..., description="The academic year"),
        semester_number: int = Query(..., ge=1, le=3, description="The semester number"),
):
    """
    Returns two separate lists of offerings for a specific semester:
    1. Scheduled: Includes session details (day, time).
    2. Unscheduled: Offerings waiting for manual or automated placement.
    Both lists now include full details about the group and target cohorts.
    """
    try:
        # 1. Fetch Master List (Includes cohorts and group_number via our new Repo function)
        all_offerings = await sq_repo.list_offerings_with_details(semester_year, semester_number)
        all_offerings = [parse_json_fields(o) for o in all_offerings]

        # 2. Fetch current sessions
        scheduled_sessions = await sq_repo.get_detailed_schedule(schedule_id=schedule_id)
        scheduled_sessions = [parse_json_fields(s) for s in scheduled_sessions]

        # 3. Create mapping for scheduled offerings
        scheduled_map = {s['offering_id']: s for s in scheduled_sessions}

        scheduled_list = []
        unscheduled_list = []

        for offering in all_offerings:
            offering_id = offering['offering_id']

            # Enrich the offering object with session data if it exists
            if offering_id in scheduled_map:
                session = scheduled_map[offering_id]
                offering_with_session = {
                    **offering,
                    "session_details": {
                        "session_id": session.get("session_id"),
                        "day_of_week": session.get("day_of_week"),
                        "start_time": session.get("start_time"),
                        "end_time": session.get("end_time")
                    }
                }
                scheduled_list.append(offering_with_session)
            else:
                # Still include the fields but with session_details as null
                offering["session_details"] = None
                unscheduled_list.append(offering)

        return {
            "scheduled": scheduled_list,
            "unscheduled": unscheduled_list,
            "total_count": len(all_offerings),
            "scheduled_count": len(scheduled_list),
            "unscheduled_count": len(unscheduled_list)
        }

    except Exception as e:
        logger.error(f"Error fetching offerings distribution: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")



@router.post(
    "/{schedule_id}/sessions",
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "description": "Manual session created/updated successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "session_id": 901,
                        "schedule_id": 10,
                        "offering_id": 120,
                        "lecturer_internal_id": 42,
                        "day_of_week": 3,
                        "start_time": "10:00:00",
                        "end_time": "13:00:00"
                    }
                }
            },
        },
        400: {"description": "Invalid time range or data conflict."},
    },
)
async def create_or_update_manual_session(
    request: Request,
    schedule_id: int = Path(..., description="The ID of the schedule"),
    payload: ManualSessionUpsertRequest = Body(
        ...,
        example={
            "offering_id": 120,
            "lecturer_internal_id": 42,
            "day_of_week": 3,
            "start_time": "10:00:00",
            "end_time": "13:00:00",
            "breaking_constraint": [
                    {
                        "constraint_id": 55,
                        "semester_year": 2026,
                        "semester_number": 1,
                        "breaking_atomic_constraints": [{
                            "atomic_constraint_index": 0,
                            "days": [3],
                            "type": "block",
                            "time_slot": { "start_hour": 10, "end_hour": 13 }
                        }]
                    },
                ],
        },
    ),
):
    """
    Create or update a manual session in courses_schedules.
    Allows the secretary to override constraints and force a specific time/day.
    Also updates the breaking_constraints table with the provided breaking constraints.
    """
    try:
        # Get schedule info to retrieve semester year and number
        schedule = await schedules_repo.get_schedule(schedule_id)
        if not schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Schedule ID {schedule_id} not found."
            )
        
        # Create or update the session
        session = await schedules_repo.upsert_manual_session(schedule_id, payload.model_dump(exclude={'breaking_constraint'}))
        
        # Update breaking constraints if any are provided
        if payload.breaking_constraint:
            await breaking_constraints_repo.create_breaking_constraints(
                breaking_constraints=payload.breaking_constraint
            )
        
        return session
    except Exception as e:
        logger.error(f"Error creating manual session: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.delete(
    "/{schedule_id}/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_scheduled_session(
    request: Request,
    schedule_id: int = Path(..., description="The ID of the schedule"),
    session_id: int = Path(..., description="The session to remove"),
):
    """
    Delete a specific session from the schedule.
    This effectively moves the course back to the 'unscheduled' list.
    """
    try:
        success = await schedules_repo.delete_session(schedule_id, session_id)
        if not success:
            raise HTTPException(status_code=404, detail="Session not found")
        return None
    except Exception as e:
        logger.error(f"Error deleting session: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))