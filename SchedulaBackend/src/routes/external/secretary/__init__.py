# src/routes/external/secretary/__init__.py

from fastapi import APIRouter
from . import setup
from . import semester
from . import schedules
from . import dashboard
from . import breaking_constraints
from . import manage_constraints
from . import fairness
secretary_router = APIRouter(
    prefix="/secretary"
)

# Include sub-routers with their own prefixes if needed
secretary_router.include_router(setup.router, prefix="/setup", tags=["Setup"])
secretary_router.include_router(semester.router, prefix="/semesters", tags=["Semesters"])
secretary_router.include_router(schedules.router, prefix="/schedules", tags=["Schedules"])
secretary_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
secretary_router.include_router(breaking_constraints.router, prefix="/breaking-constraints", tags=["Breaking Constraints"])
secretary_router.include_router(manage_constraints.router, prefix="/manage-constraints", tags=["Manage Constraints"])
secretary_router.include_router(fairness.router, prefix="/fairness", tags=["Fairness"])
__all__ = ["secretary_router"]
