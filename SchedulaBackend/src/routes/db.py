from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse, JSONResponse
from typing import Dict, List
from pathlib import Path

from src.database.database import db

router = APIRouter(prefix="/db", tags=["database"])


def _split_sql_script(sql_text: str) -> List[str]:
    """Split SQL script into statements, preserving DO $$...$$; blocks.

    This handles semicolons inside dollar-quoted blocks so they aren't split.
    """
    statements: List[str] = []
    buf: List[str] = []
    in_dollar: bool = False

    for line in sql_text.splitlines():
        buf.append(line)
        stripped = line.strip()

        # Detect start of dollar-quoted block (e.g., DO $$ or DO $tag$)
        if not in_dollar and (stripped.startswith("DO $$") or stripped.startswith("DO $") or " AS $$" in stripped):
            in_dollar = True

        # End of a dollar-quoted block: line containing $$; (allow spaces)
        if in_dollar and "$$;" in stripped:
            in_dollar = False
            statements.append("\n".join(buf).strip())
            buf = []
            continue

        # Normal statement termination by semicolon, only when not in dollar block
        if not in_dollar and stripped.endswith(";"):
            statements.append("\n".join(buf).strip())
            buf = []

    # Any trailing buffer
    if buf:
        residual = "\n".join(buf).strip()
        if residual:
            statements.append(residual)
    return statements


@router.post(
    "/init",
    response_class=PlainTextResponse,
    responses={
        200: {
            "description": "Database initialized successfully",
            "content": {"text/plain": {"example": "Database initialized"}},
        },
        500: {
            "description": "Initialization failed",
            "content": {
                "application/json": {
                    "example": {"detail": "init_db.sql not found"}
                }
            },
        },
    },
)
async def init_db():
    sql_path = Path(__file__).parents[1] / "database" / "init_db.sql"
    if not sql_path.exists():
        raise HTTPException(status_code=500, detail="init_db.sql not found")

    sql_text = sql_path.read_text(encoding="utf-8")
    statements = _split_sql_script(sql_text)

    async with db.transaction() as conn:
        for stmt in statements:
            # Skip empty lines/statements just in case
            s = stmt.strip()
            if not s:
                continue
            await conn.execute(s)

    return "Database initialized"


@router.delete(
    "/clear",
    response_class=PlainTextResponse,
    responses={
        200: {
            "description": "Database cleared successfully",
            "content": {"text/plain": {"example": "Database cleared"}},
        },
        500: {
            "description": "Clear operation failed",
            "content": {
                "application/json": {
                    "example": {"detail": "Failed to clear database"}
                }
            },
        },
    },
)
async def clear_db():
    """Empty all tables in the database while preserving the schema."""
    try:
        async with db.transaction() as conn:
            await conn.execute("""
                TRUNCATE TABLE 
                    users,
                    user_notifications,
                    courses,
                    course_offering,
                    offering_cohorts,
                    lecturer_courses,
                    semesters,
                    schedules,
                    lecturer_constraints,
                    breaking_constraints,
                    courses_schedules,
                    schedule_approvals,
                    fairness_reports,
                    solver_runs
                RESTART IDENTITY CASCADE
            """)
        return "Database cleared"
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to clear database: {str(e)}"
        )



@router.get(
    "/health",
    responses={
        200: {
            "description": "Database health status",
            "content": {
                "application/json": {
                    "example": {
                        "connected": True,
                        "tables_present": ["users", "courses"],
                        "missing_tables": [],
                        "ok": True,
                    }
                }
            },
        },
        500: {
            "description": "Database health check failed",
            "content": {
                "application/json": {
                    "example": {
                        "connected": False,
                        "error": "connection timeout",
                        "ok": False,
                    }
                }
            },
        },
    },
)
async def db_health():
    try:
        row = await db.fetch_one("SELECT 1 AS ok")
        connected = bool(row and row.get("ok") == 1)

        required = {
            "users",
            "user_notifications",
            "courses",
            "course_offering",
            "offering_cohorts",
            "lecturer_courses",
            "semesters",
            "schedules",
            "lecturer_constraints",
            "breaking_constraints",
            "courses_schedules",
            "schedule_approvals",
            "fairness_reports",
            "solver_runs"
        }

        tables = await db.fetch_all(
            """
            SELECT tablename
            FROM pg_tables
            WHERE schemaname = 'public' AND tablename = ANY($1)
            """,
            list(required),
        )
        present = {str(r.get("tablename")) for r in tables if r.get("tablename") is not None}
        missing = list(required - present)

        status = {
            "connected": connected,
            "tables_present": list(present),
            "missing_tables": missing,
            "ok": connected and not missing,
        }
        return JSONResponse(status)
    except Exception as e:
        return JSONResponse({"connected": False, "error": str(e), "ok": False}, status_code=500)
