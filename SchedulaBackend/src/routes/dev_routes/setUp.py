# src/routes/dev_routes/setUp.py
"""DEV ONLY - Bulk data load helpers (mirror of /secretary/setup)."""

from fastapi import APIRouter, HTTPException, status, UploadFile, File
from typing import Any, Dict

from src.input_convertor.converter import load_static_data, load_assignments
from src.input_convertor.test_converter import test_and_export_excel


router = APIRouter()


@router.post(
    "/load_data",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Static data (users and courses) loaded into DB.",
            "content": {
                "application/json": {"example": {"status": "success", "users_loaded": 150, "courses_loaded": 25}}
            },
        },
        400: {
            "description": "File processing error or invalid format.",
            "content": {"application/json": {"example": {"detail": "Missing required column in Excel file."}}},
        },
    },
)
async def load_initial_data(
    lecturers_dedu_file: UploadFile = File(
        ...,
        description="Deduplicated Excel file containing lecturer identity data only (no course/semester columns).",
    ),
    courses_file: UploadFile = File(..., description="Excel file containing course data."),
) -> Dict[str, Any]:
    """
    Loads static, semester-independent data: users (lecturers) and courses.
    Expects the slim deduplicated lecturer file (lecturer_dedu.xlsx).
    Run this once before /load_assignments.
    """
    lecturers_dedu_bytes = await lecturers_dedu_file.read()
    courses_bytes = await courses_file.read()
    return await load_static_data(lecturers_dedu_bytes, courses_bytes)


@router.post(
    "/load_assignments",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Assignment data (offerings, cohorts, lecturer-course links) loaded into DB.",
            "content": {
                "application/json": {"example": {"status": "success", "offerings_loaded": 30, "lecturer_courses_loaded": 45}}
            },
        },
        400: {
            "description": "File processing error or invalid format / semester missing.",
            "content": {"application/json": {"example": {"detail": "Semester 2026/1 not found in DB. Please create it first."}}},
        },
    },
)
async def load_semester_assignments(
    lecturers_file: UploadFile = File(..., description="Full lecturer Excel file (with course/semester assignment columns)."),
    courses_file: UploadFile = File(..., description="Excel file containing course data."),
) -> Dict[str, Any]:
    """
    Loads semester-specific assignment data: course offerings (with cohorts)
    and lecturer-course links. Requires /load_data to have been run first so
    users and courses already exist.
    """
    lecturers_bytes = await lecturers_file.read()
    courses_bytes = await courses_file.read()
    res = await load_assignments(lecturers_bytes, courses_bytes)
    if res.get("status") == "failure":
        raise HTTPException(status_code=400, detail=res.get("detail", "Unknown error during assignment loading."))
    return res


@router.post(
    "/load_data_test",
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Test completed - data exported to Excel file.",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "message": "Test data exported...",
                        "users_count": 150,
                        "courses_count": 25,
                        "offerings_count": 30,
                        "lecturer_courses_count": 45,
                    }
                }
            },
        },
    },
)
async def load_data_test(
    lecturers_file: UploadFile = File(..., description="Full lecturer Excel file (with course/semester assignment columns)."),
    courses_file: UploadFile = File(..., description="Excel file containing course data."),
) -> Dict[str, Any]:
    """
    Runs the full mapping pipeline without touching the DB and writes the
    resulting tables to /tmp/test_output.xlsx so the mapping logic can be
    inspected.
    """
    lecturers_bytes = await lecturers_file.read()
    courses_bytes = await courses_file.read()
    return await test_and_export_excel(lecturers_bytes, courses_bytes, "/tmp/test_output.xlsx")
