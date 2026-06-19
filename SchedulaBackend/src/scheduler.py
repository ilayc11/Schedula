"""
Scheduler for automated tasks like nightly solver runs.

This module uses APScheduler to schedule recurring tasks such as:
- Nightly solver runs for active semesters
- Cleanup tasks
- Report generation
"""
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.notifications.period_events import run_period_transition_checks
from src.repositories import solver_runs as solver_runs_repo
from src.rabbitmq.rabbitmq import rabbitmq
from src.database.database import db

logger = logging.getLogger(__name__)

# Initialize scheduler
scheduler = AsyncIOScheduler()
SCHEDULER_TIMEZONE = "UTC"

REQUEST_QUEUE_NAME = "constraints_request_queue"


async def get_active_semesters():
    """
    Fetch semesters that are in an active state and should have solver runs.
    
    Returns semesters with status 'SUB' (Submission) or 'REV' (Review).
    These are the states where constraints are being collected and
    schedules need to be generated.
    """
    query = """
        SELECT semester_year, semester_number, status
        FROM semesters
        WHERE status IN ('SUB', 'REV', 'CHA')
        ORDER BY semester_year DESC, semester_number DESC
    """
    
    rows = await db.fetch_all(query)
    return [{"year": row["semester_year"], "number": row["semester_number"]} for row in rows]


async def nightly_solver_run():
    """
    Scheduled task to run solver for all active semesters.
    
    This runs every night at 2:00 AM to ensure schedules are up-to-date
    with the latest constraints.
    """
    try:
        logger.info("Starting nightly scheduled solver runs...")
        
        # Get active semesters
        active_semesters = await get_active_semesters()
        
        if not active_semesters:
            logger.info("No active semesters found for scheduled solver run")
            return
        
        logger.info(f"Found {len(active_semesters)} active semester(s) for scheduled solver run")
        
        # Trigger solver for each active semester
        for semester in active_semesters:
            year = semester["year"]
            number = semester["number"]
            
            try:
                # Create a solver run record
                run = await solver_runs_repo.create_run(year, number)
                
                if run:
                    # Publish message to RabbitMQ to trigger solver
                    await rabbitmq.publish(REQUEST_QUEUE_NAME, {
                        "semester_year": year,
                        "semester_number": number,
                        "run_id": run["run_id"],
                        "trigger_type": "scheduled"
                    })
                    
                    logger.info(
                        f"Scheduled solver run triggered for semester {year}/{number}, "
                        f"run_id={run['run_id']}"
                    )
                else:
                    logger.error(f"Failed to create solver run record for semester {year}/{number}")
                    
            except Exception as e:
                logger.error(
                    f"Error triggering scheduled solver for semester {year}/{number}: {str(e)}",
                    exc_info=True
                )
        
        logger.info(f"Completed nightly scheduled solver runs for {len(active_semesters)} semester(s)")
        
    except Exception as e:
        logger.error(f"Error in nightly solver run task: {str(e)}", exc_info=True)


async def periodic_transition_check_run():
    """Scheduled task that checks semester period transitions and publishes notifications."""
    try:
        logger.info("Starting periodic semester transition check...")
        await run_period_transition_checks(source="scheduler")
        logger.info("Completed periodic semester transition check")
    except Exception as e:
        logger.error(f"Error in periodic transition check task: {str(e)}", exc_info=True)


def start_scheduler():
    """
    Start the scheduler and register all scheduled tasks.
    
    This should be called when the FastAPI app starts.
    """
    # Schedule nightly solver run at 2:00 AM
    scheduler.add_job(
        nightly_solver_run,
        trigger=CronTrigger(hour=2, minute=0, timezone=SCHEDULER_TIMEZONE),
        id="nightly_solver_run",
        name="Nightly Solver Run",
        replace_existing=True
    )

    scheduler.add_job(
        periodic_transition_check_run,
        trigger=CronTrigger(minute="*/30", timezone=SCHEDULER_TIMEZONE),
        id="period_transition_check",
        name="Period Transition Check",
        replace_existing=True,
    )
    
    logger.info("Scheduled tasks registered:")
    logger.info("  - Nightly Solver Run: 02:00 AM daily (UTC)")
    logger.info("  - Period Transition Check: every 30 minutes (UTC)")
    
    # Start the scheduler
    scheduler.start()
    logger.info("Scheduler started successfully")


def stop_scheduler():
    """
    Stop the scheduler gracefully.
    
    This should be called when the FastAPI app shuts down.
    """
    if scheduler.running:
        scheduler.shutdown(wait=True)
        logger.info("Scheduler stopped")


# For testing/manual triggering
async def trigger_manual_test():
    """
    Manually trigger the nightly solver run task for testing.
    Can be called from API endpoint or CLI.
    """
    logger.info("Manually triggering nightly solver run task...")
    await nightly_solver_run()

