# src/routes/lecturer/__init__.py
from fastapi import APIRouter
from . import constraints
from . import schedules
from . import dashboard
from . import notifications

lecturer_router = APIRouter(
    prefix="/lecturer")

lecturer_router.include_router(
    constraints.router,
    prefix="/constraints",
    tags=["Lecturer Constraints"]
)

lecturer_router.include_router(
    schedules.router,
    prefix="/schedules",
    tags=["Lecturer Schedules"]
)

lecturer_router.include_router(
    dashboard.router,
    prefix="/dashboard",
    tags=["Lecturer Dashboard"]
)

lecturer_router.include_router(
    notifications.router,
    prefix="/notifications",
    tags=["Lecturer Notifications"]
)

__all__ = ["lecturer_router"]
