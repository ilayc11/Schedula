import asyncio
import os
import json
import logging
import time
from aio_pika import connect_robust, Message
from aio_pika.abc import AbstractRobustConnection, AbstractChannel, AbstractIncomingMessage
from src.db import db
from src.solver import CSPSolver

# Configuration
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://rabbitmq:rabbitmq@rabbitmq:5672/")
REQUEST_QUEUE_NAME = "constraints_request_queue"
RESPONSE_QUEUE_NAME = "constraints_response_queue"

# Batching configuration
BATCH_TIMEOUT_SECONDS = 1.5  # Reduced from 5s - max time to wait after last message
MAX_BATCH_SIZE = 100  # Process immediately if batch reaches this size
MAX_BATCH_WAIT_SECONDS = 3.0  # Max time to wait from first message, regardless of new messages

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SolverService:
    """Event-driven solver service using RabbitMQ consumer pattern."""
    
    def __init__(self, rabbitmq_url: str):
        self.rabbitmq_url = rabbitmq_url
        self.connection: AbstractRobustConnection | None = None
        self.channel: AbstractChannel | None = None
        self.pending_batch: list = []
        self.batch_lock = asyncio.Lock()
        self.batch_timer_task = None
        self.batch_start_time = None  # Track when first message arrived
        
    async def start(self):
        """Start the event-driven solver service."""
        logger.info("Solver Service Started.")
        
        # Initialize Database Connection
        try:
            await db.connect()
            logger.info("Database connected successfully.")
        except Exception as e:
            logger.error(f"Could not connect to database: {e}")
            raise
        
        try:
            # Use connect_robust for automatic reconnection
            self.connection = await connect_robust(self.rabbitmq_url)
            logger.info(f"Connected to RabbitMQ at {self.rabbitmq_url}")
            
            async with self.connection:
                self.channel = await self.connection.channel()
                
                # Process one message at a time to prevent overwhelming the solver
                # Adjust prefetch_count if solver can handle parallel processing
                await self.channel.set_qos(prefetch_count=1)
                
                # Declare queues
                request_queue = await self.channel.declare_queue(
                    REQUEST_QUEUE_NAME,
                    durable=True
                )
                response_queue = await self.channel.declare_queue(
                    RESPONSE_QUEUE_NAME,
                    durable=True
                )
                
                logger.info(f"Listening on queue '{REQUEST_QUEUE_NAME}', waiting for constraint updates...")
                
                # Event-driven consumption - blocks until messages arrive
                async with request_queue.iterator() as queue_iter:
                    async for message in queue_iter:
                        await self._handle_message(message, response_queue)
                        
        except asyncio.CancelledError:
            logger.info("Solver service stopping...")
            raise
        except Exception as e:
            logger.error(f"Fatal error in solver service: {e}", exc_info=True)
            raise
        finally:
            await db.close()
            logger.info("Database connection closed.")
    
    async def _handle_message(self, message: AbstractIncomingMessage, response_queue):
        """Handle incoming constraint update message with batching optimization.
        
        Each message represents a single lecturer's constraint update.
        Multiple updates for the same semester are batched together.
        """
        async with self.batch_lock:
            try:
                # Decode and validate message
                body = json.loads(message.body.decode())
                logger.info(
                    f"Received constraint update: constraint_id={body.get('new_constraint_id')}, "
                    f"lecturer={body.get('lecturer_id')}, "
                    f"semester={body.get('semester_year')}/{body.get('semester_number')}"
                )
                
                # Track first message time
                if not self.pending_batch:
                    self.batch_start_time = time.time()
                
                # Add to pending batch
                self.pending_batch.append({
                    'message': message,
                    'data': body
                })
                
                # Check if we should process immediately
                batch_size = len(self.pending_batch)
                time_since_first = time.time() - self.batch_start_time if self.batch_start_time else 0
                
                # Process immediately if:
                # 1. Batch size limit reached
                # 2. Max wait time from first message exceeded
                if batch_size >= MAX_BATCH_SIZE or time_since_first >= MAX_BATCH_WAIT_SECONDS:
                    logger.info(
                        f"Processing batch immediately: size={batch_size}/{MAX_BATCH_SIZE}, "
                        f"wait_time={time_since_first:.1f}s/{MAX_BATCH_WAIT_SECONDS}s"
                    )
                    # Cancel timer if running
                    if self.batch_timer_task and not self.batch_timer_task.done():
                        self.batch_timer_task.cancel()
                    # Process now
                    await self._process_batch(response_queue)
                else:
                    # Cancel existing timer if any
                    if self.batch_timer_task and not self.batch_timer_task.done():
                        self.batch_timer_task.cancel()
                    
                    # Start new timer to process batch
                    self.batch_timer_task = asyncio.create_task(
                        self._batch_timer(response_queue)
                    )
                
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in message: {e}")
                await message.reject(requeue=False)
            except Exception as e:
                logger.error(f"Error handling message: {e}", exc_info=True)
                await message.reject(requeue=True)
    
    async def _batch_timer(self, response_queue):
        """Wait for additional messages before processing batch."""
        try:
            await asyncio.sleep(BATCH_TIMEOUT_SECONDS)
            await self._process_batch(response_queue)
        except asyncio.CancelledError:
            # Timer was cancelled, new message arrived
            pass
    
    async def _process_batch(self, response_queue):
        """Process accumulated batch of messages."""
        async with self.batch_lock:
            if not self.pending_batch:
                return
            
            batch = self.pending_batch.copy()
            self.pending_batch.clear()
            
        logger.info(f"Processing batch of {len(batch)} constraint update(s)")
        
        # Identify unique semesters that need re-solving
        # Multiple constraint updates for same semester = solve once.
        # We also collect the highest non-null schedule_id advertised by the
        # batch so the solver writes to the most recent draft the API
        # returned to its caller.
        semesters_to_solve = set()
        messages_by_semester = {}
        requested_schedule_ids = {}
        
        for item in batch:
            data = item['data']
            year = data.get('semester_year')
            number = data.get('semester_number')
            schedule_id = data.get('schedule_id')
            
            if year and number:
                semester_key = (year, number)
                semesters_to_solve.add(semester_key)
                
                if semester_key not in messages_by_semester:
                    messages_by_semester[semester_key] = []
                messages_by_semester[semester_key].append(item['message'])

                if isinstance(schedule_id, int):
                    current = requested_schedule_ids.get(semester_key)
                    if current is None or schedule_id > current:
                        requested_schedule_ids[semester_key] = schedule_id
        
        logger.info(f"Solving for {len(semesters_to_solve)} unique semesters")
        
        # Solve each unique semester
        for year, number in semesters_to_solve:
            try:
                semester_key = (year, number)
                await self._solve_semester(
                    year,
                    number,
                    response_queue,
                    requested_schedule_id=requested_schedule_ids.get(semester_key),
                )
                
                # Acknowledge all messages for this semester
                for msg in messages_by_semester[semester_key]:
                    await msg.ack()
                    
            except Exception as e:
                logger.error(f"Error solving semester {year}/{number}: {e}", exc_info=True)
                # Reject messages to requeue them
                for msg in messages_by_semester[(year, number)]:
                    await msg.reject(requeue=True)
    
    async def _solve_semester(
        self,
        year: int,
        number: int,
        response_queue,
        requested_schedule_id: int | None = None,
    ):
        """Solve constraints for a single semester.

        ``requested_schedule_id`` is the ``schedule_id`` advertised by the
        triggering API call (if any). When provided and valid, the solver
        writes its solution to that exact draft so the row returned to the
        caller ends up holding the new sessions.
        """
        logger.info(
            f"Starting solver for Semester {year}-{number} "
            f"(requested_schedule_id={requested_schedule_id})..."
        )
        start_time = time.time()
        
        # 0. Clean stale breaking constraints (invalid atomic indices from edited constraints)
        await db.clean_stale_breaking_constraints(year, number)
        
        # 1. Fetch Semester Data (Offerings + Constraints)
        semester_data = await db.get_semester_data(year, number)
        logger.info(
            f"Fetched {len(semester_data['offerings'])} offerings and "
            f"{len(semester_data['constraints'])} constraint sets."
        )
        
        # 2. Solve
        solver = CSPSolver()
        result = solver.solve(semester_data)
        
        duration = time.time() - start_time
        logger.info(f"Solver finished in {duration:.4f} seconds.")
        
        # 3. Handle Result
        schedule_id = await db.get_or_create_draft_schedule(
            year, number, requested_schedule_id=requested_schedule_id
        )
        
        response_body: dict[str, int | str | list] = {
            "schedule_id": schedule_id,
            "semester_year": year,
            "semester_number": number,
        }
        
        if result['status'] == 'solved':
            # Save successful solution
            solution = result['solution']
            await db.save_solution(schedule_id, solution)
            logger.info(f"Successfully saved solution for Schedule ID {schedule_id}.")
            
            # Remove breaking constraints for constraints that are no longer breaking
            used_constraint_ids = result.get('used_constraint_ids', [])
            if used_constraint_ids:
                await db.remove_resolved_constraints(year, number, used_constraint_ids)
            
            response_body["status"] = "solved"
            response_body["solution_count"] = len(solution)
        else:
            # Handle failure - save all breaking constraints (upsert, no duplicates)
            conflict_constraints = result.get('conflict_constraints', [])
            failure_reason = result.get('failure_reason')
            logger.warning(
                f"Solver failed for semester {year}/{number} "
                f"(reason={failure_reason}). "
                f"Found {len(conflict_constraints)} breaking constraint(s)"
            )

            # Save breaking constraints to database (ON CONFLICT DO NOTHING handles duplicates)
            if conflict_constraints:
                await db.save_breaking_constraints(year, number, conflict_constraints)

            response_body["status"] = "failed"
            response_body["broken_constraints"] = conflict_constraints
            # Propagate the structured failure reason and (when applicable)
            # the data-infeasibility breakdown so the API can give the user
            # an actionable message instead of a vague "schedule failed".
            if failure_reason:
                response_body["failure_reason"] = failure_reason
            if failure_reason == "data_infeasible":
                response_body["infeasible_cohorts"] = result.get("infeasible_cohorts", [])
                response_body["infeasible_lecturers"] = result.get("infeasible_lecturers", [])
                response_body["weekly_capacity_hours"] = result.get("weekly_capacity_hours")
        
        # Publish completion message
        if self.channel:
            await self.channel.default_exchange.publish(
                Message(body=json.dumps(response_body).encode()),
                routing_key=response_queue.name
            )
            logger.info(f"Published solution event to {response_queue.name}")
        else:
            logger.error("Channel is not initialized, cannot publish response")


async def main():
    """Main entry point for the solver service."""
    solver_service = SolverService(RABBITMQ_URL)
    await solver_service.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
