# src/routes/secretary/setup.py

import logging

from fastapi import APIRouter, HTTPException, status, Request, UploadFile, File
from typing import Dict, Any
from src.input_convertor.converter import load_static_data, load_assignments
from src.input_convertor.test_converter import test_and_export_excel


logger = logging.getLogger(__name__)
router = APIRouter()


def _friendly_upload_error(exc: Exception) -> HTTPException:
    """Translate a raw converter/parsing exception into a user-friendly HTTP error.

    The original exception is always logged (with traceback) for debugging;
    the secretary only ever sees a clean, actionable message instead of a raw
    pandas/asyncpg/KeyError string.
    """
    logger.error("Semester data upload failed: %s", exc, exc_info=True)

    # Missing/renamed column the mapper expected (config column lookups).
    if isinstance(exc, KeyError):
        missing = str(exc).strip("'\"")
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"The uploaded file is missing an expected column ({missing}). "
                "Please use the standard template and check the column headers."
            ),
        )

    # Unreadable / corrupt / wrong-format spreadsheet (pandas raises ValueError).
    if isinstance(exc, ValueError):
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "We couldn't read one of the uploaded files. Make sure both files "
                "are valid Excel files (.xlsx or .xls) exported from the standard template."
            ),
        )

    # Anything else is unexpected — keep the detail generic.
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=(
            "Something went wrong while processing the uploaded files. "
            "Please try again, and contact support if the problem persists."
        ),
    )


@router.post(
    "/load_data",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Static data (users and courses) loaded into DB.",
            "content": {
                "application/json": {"example": {"status": "success", "users_loaded": 150, "courses_loaded": 25}}},
        },
        400: {
            "description": "File processing error or invalid format.",
            "content": {"application/json": {"example": {"detail": "Missing required column in Excel file."}}},
        },
        403: {
            "description": "Forbidden - User is not a Secretary",
            "content": {"application/json": {"example": {"detail": "User does not have Secretary privileges"}}},
        },
    },
)
async def load_initial_data(
        request: Request,
        lecturers_dedu_file: UploadFile = File(..., description="Deduplicated Excel file containing lecturer identity data only (no course/semester columns)."),
        courses_file: UploadFile = File(..., description="Excel file containing course data."),
) -> Dict[str, Any]:
    """
    Loads static, semester-independent data: users (lecturers) and courses.
    Expects the slim deduplicated lecturer file (lecturer_dedu.xlsx).
    Run this once before /load_assignments.
    """
    lecturers_dedu_bytes = await lecturers_dedu_file.read()
    courses_bytes = await courses_file.read()
    try:
        return await load_static_data(lecturers_dedu_bytes, courses_bytes)
    except HTTPException:
        raise
    except Exception as exc:
        raise _friendly_upload_error(exc)


@router.post(
    "/load_assignments",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Assignment data (offerings, cohorts, lecturer-course links) loaded into DB.",
            "content": {
                "application/json": {"example": {"status": "success", "offerings_loaded": 30, "lecturer_courses_loaded": 45}}},
        },
        400: {
            "description": "File processing error or invalid format.",
            "content": {"application/json": {"example": {"detail": "Missing required column in Excel file."}}},
        },
        403: {
            "description": "Forbidden - User is not a Secretary",
            "content": {"application/json": {"example": {"detail": "User does not have Secretary privileges"}}},
        },
    },
)
async def load_semester_assignments(
        request: Request,
        lecturers_file: UploadFile = File(..., description="Excel file containing lecturers/users data."),
        courses_file: UploadFile = File(..., description="Excel file containing course data."),
) -> Dict[str, Any]:
    """
    Loads semester-specific assignment data: course offerings (with cohorts)
    and lecturer-course links. Requires /load_data to have been run first.
    Note: If the semester is not in the DB, raise an error to make sure the data of the relevant semester is first added.
    """
    lecturers_bytes = await lecturers_file.read()
    courses_bytes = await courses_file.read()
    try:
        res = await load_assignments(lecturers_bytes, courses_bytes)
    except HTTPException:
        raise
    except Exception as exc:
        raise _friendly_upload_error(exc)
    if res.get("status") == "failure":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=res.get("detail", "Unknown error during assignment loading."),
        )
    return res


@router.post(
    "/load_data_test",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Test completed - data exported to Excel file.",
            "content": {
                "application/json": {"example": {"status": "success", "message": "Test data exported...", "users_count": 150, "courses_count": 25, "offerings_count": 30, "lecturer_courses_count": 45}}},
        },
    },
)
async def load_data_test(
        request: Request,
        lecturers_file: UploadFile = File(..., description="Excel file containing lecturers/users data."),
        courses_file: UploadFile = File(..., description="Excel file containing course data."),
) -> Dict[str, Any]:
    """
    TEST ENDPOINT: Processes Excel files through the converter pipeline
    and exports mapped data to an Excel file with multiple sheets (users, courses, offerings, lecturer_courses).
    Does NOT call the database - just verifies the mapping logic.
    """
    lecturers_bytes = await lecturers_file.read()
    courses_bytes = await courses_file.read()

    try:
        return await test_and_export_excel(lecturers_bytes, courses_bytes, "/tmp/test_output.xlsx")
    except HTTPException:
        raise
    except Exception as exc:
        raise _friendly_upload_error(exc)