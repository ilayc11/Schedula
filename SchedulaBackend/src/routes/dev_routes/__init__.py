"""
DEV ONLY - Database routes for testing and development
DO NOT USE IN PRODUCTION
"""

from fastapi import APIRouter
from .breaking_constraints import router as breaking_constraints_router
from .constraints import router as constraints_router
from .course_offering import router as course_offering
from .courses import router as courses_router
from .courses_schedules import router as courses_schedules_router
from .fairness_reports import router as fairness_reports_router
from .lecturer_courses import router as lecturer_courses_router
from .period_notifications import router as period_notifications_router
from .schedule_approvals import router as schedule_approvals_router
from .schedules import router as schedules_router
from .semesters import router as semesters_router
from .telegram_webhook import router as telegram_webhook_router
from .user_notifications import router as user_notifications_router
from .users import router as users_router
from .solver_runs import router as solver_runs_router
from .dashboard import router as dashboard_router
from .setUp import router as setup_router

# Main dev router that includes all sub-routers
dev_router = APIRouter(prefix="/dev")

dev_router.include_router(breaking_constraints_router, prefix="/breaking-constraints", tags=["DEV - Breaking Constraints"])
dev_router.include_router(constraints_router, prefix="/constraints", tags=["DEV - Constraints"])
dev_router.include_router(course_offering, prefix="/course-offering", tags=["DEV - Course Offering"])
dev_router.include_router(courses_router, prefix="/courses", tags=["DEV - Courses"])
dev_router.include_router(courses_schedules_router, prefix="/courses-schedules", tags=["DEV - Courses Schedules"])
dev_router.include_router(dashboard_router, prefix="/dashboard", tags=["DEV - Dashboard"])
dev_router.include_router(fairness_reports_router, prefix="/fairness-reports", tags=["DEV - Fairness Reports"])
dev_router.include_router(lecturer_courses_router, prefix="/lecturer-courses", tags=["DEV - Lecturer Courses"])
dev_router.include_router(period_notifications_router, prefix="/period-notifications", tags=["DEV - Period Notifications"])
dev_router.include_router(schedule_approvals_router, prefix="/schedule-approvals", tags=["DEV - Schedule Approvals"])
dev_router.include_router(schedules_router, prefix="/schedules", tags=["DEV - Schedules"])
dev_router.include_router(semesters_router, prefix="/semesters", tags=["DEV - Semesters"])
dev_router.include_router(solver_runs_router, prefix="/solver-runs", tags=["DEV - Solver Runs"])
dev_router.include_router(telegram_webhook_router, prefix="/telegram-webhook", tags=["DEV - Telegram Webhook"])
dev_router.include_router(user_notifications_router, prefix="/user-notifications", tags=["DEV - User Notifications"])
dev_router.include_router(users_router, prefix="/users", tags=["DEV - Users"])
dev_router.include_router(setup_router, prefix="/setUp", tags=["DEV - SetUp"])
