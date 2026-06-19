"""
Integration tests for solver pipeline.

Tests the full message processing pipeline and RabbitMQ integration.
"""
import pytest
import asyncio
import json
import logging
from aio_pika import connect, Message, DeliveryMode
from src.main import SolverService
import src.main
from src.db import db
from datetime import datetime


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skip(reason="RabbitMQ queue persistence issue in test environment - message not persisting after publish")
async def test_end_to_end_pipeline(rabbitmq_url, database_url, purge_rabbitmq_queues):
    """
    Test the full pipeline:
    RabbitMQ -> Worker (process_queue) -> DB Fetch -> Solver -> DB Save
    """
    
    # 1. Setup DB Data (Constraint)
    # Ensure db is connected
    if not db.pool:
        db.url = database_url
        await db.connect()
    
    # Insert Test Data manually for the worker to find
    async with db.pool.acquire() as conn:
        # Ensure User
        await conn.execute("""
              INSERT INTO users (user_internal_id, user_name, user_id, first_name, last_name, email, role)
              OVERRIDING SYSTEM VALUE
              VALUES (9002, 'test_pipeline', '000099998', 'Pipe', 'Line', 'pipe@test.com', 'L')
              ON CONFLICT DO NOTHING
        """)
        
        # Insert Test Semester
        await conn.execute("""
              INSERT INTO semesters (
                  semester_year, semester_number, 
                  semester_start_date, semester_end_date, 
                  constraint_start_date, constraint_end_date, 
                  change_period_start, change_period_end, 
                  status
              ) VALUES (
                  9999, 1, 
                  '9999-01-01', '9999-04-01', 
                  '9999-01-01', '9999-02-01', 
                  '9999-02-01', '9999-03-01', 
                  'SET'
              ) ON CONFLICT DO NOTHING
        """)
        
        # Insert Constraint with valid structure matching LLM pipeline output
        # structured_rules should be: {"atomic_constraints": [...]}
        rules_json = json.dumps({
            "atomic_constraints": [
                {
                    "type": "block",
                    "days": [3],
                    "time_slot": {"start_hour": 9, "end_hour": 12}
                }
            ]
        })
        
        await conn.execute("""
            INSERT INTO lecturer_constraints 
            (lecturer_internal_id, semester_year, semester_number, raw_text, structured_rules)
            VALUES (9002, 9999, 1, 'Pipeline Test', $1::jsonb)
        """, rules_json)

# 2. & 3. Publish and Retrieve Message (using same connection to avoid timing issues)
    connection = await connect(rabbitmq_url)
    channel = await connection.channel()

    # Declare the queue first to ensure it exists
    queue = await channel.declare_queue("constraints_request_queue", durable=True)
    response_queue = await channel.declare_queue("constraints_response_queue", durable=True)
    
    print(f"Queue declared: {queue.name}")

    msg_body = {
        "semester_year": 9999,
        "semester_number": 1,
        "new_constraint_id": 123,
        "lecturer_id": 9002
    }

    message_to_publish = Message(
        body=json.dumps(msg_body).encode(),
        delivery_mode=DeliveryMode.PERSISTENT
    )

    # Publish message
    await channel.default_exchange.publish(
        message_to_publish,
        routing_key="constraints_request_queue"
    )

    print(f"Message published to queue")

    # Get one message and process it (using same channel/connection)
    message = await queue.get(timeout=5, fail=False)

    assert message is not None, "Message should be in queue"
    
    # Create solver service to handle the message
    solver_service = SolverService(rabbitmq_url)
    solver_service.connection = connection
    solver_service.channel = channel
    
    await solver_service._handle_message(message, response_queue)
    
    # Wait for batch processing to complete
    # BATCH_TIMEOUT_SECONDS = 1.5, MAX_BATCH_WAIT_SECONDS = 3.0
    await asyncio.sleep(5.0)  # Wait for batch timer to trigger
    
    # Wait for the batch timer task to complete if it exists
    if solver_service.batch_timer_task and not solver_service.batch_timer_task.done():
        try:
            await asyncio.wait_for(solver_service.batch_timer_task, timeout=2.0)
        except asyncio.TimeoutError:
            pass
    
    # Force process any pending batch that hasn't been processed yet
    if solver_service.pending_batch:
        print(f"Force processing {len(solver_service.pending_batch)} pending messages")
        await solver_service._process_batch(response_queue)
    
    await connection.close()
    
    # 4. Verify DB Result
    # Check if a schedule was created/updated
    async with db.pool.acquire() as conn:
        schedule = await conn.fetchrow("""
            SELECT schedule_id, last_update 
            FROM schedules 
            WHERE semester_year = 9999 AND semester_number = 1
        """)
        
        # Debug: Check what's in the database
        if schedule is None:
            # Check if semester exists
            semester = await conn.fetchrow("SELECT * FROM semesters WHERE semester_year = 9999 AND semester_number = 1")
            print(f"Semester exists: {semester is not None}")
            
            # Check if constraint exists
            constraint = await conn.fetchrow("SELECT * FROM lecturer_constraints WHERE semester_year = 9999 AND semester_number = 1")
            print(f"Constraint exists: {constraint is not None}")
            
            # Check if there are any schedules at all
            all_schedules = await conn.fetch("SELECT * FROM schedules")
            print(f"Total schedules in DB: {len(all_schedules)}")
        
        assert schedule is not None, "Schedule should have been created"
        
        # Verify courses_schedules
        # Note: If no courses exist in DB for this semester, count will be 0, but it should succeed (empty schedule).
        # To make it more realistic, we should insert courses/offerings, but for pipeline smoke test, 
        # just verifying it ran and created a schedule record is sufficient proof the plumbing works.
   
    # Don't close db here as it might be used by other tests
    # await db.close()


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skip(reason="RabbitMQ queue persistence issue in test environment - message not persisting after publish")
async def test_pipeline_reliability(rabbitmq_url, database_url, monkeypatch, purge_rabbitmq_queues):
    """
    Test pipeline reliability:
    1. Publish valid message -> Process -> Check DB (Success path)
    2. Publish invalid JSON -> Process -> Should not crash, should reject/ack.
    """
    # Patch the global RABBITMQ_URL in src.main
    monkeypatch.setattr(src.main, "RABBITMQ_URL", rabbitmq_url)
    
    db.url = database_url
    await db.connect()
    
    # 1. Publish Invalid Message (Malformed JSON)
    connection = await connect(rabbitmq_url)
    channel = await connection.channel()
    
    await channel.default_exchange.publish(
        Message(body=b"NOT JSON", delivery_mode=DeliveryMode.PERSISTENT),
        routing_key="constraints_request_queue"
    )
    
    # 2. Run Process Queue
    # It should log error but not crash, and reject the bad message
    solver_service = SolverService(rabbitmq_url)
    solver_service.connection = await connect(rabbitmq_url)
    solver_service.channel = await solver_service.connection.channel()
    
    # Re-declare queue (already declared above, but service needs its own channel)
    queue = await solver_service.channel.declare_queue(
        "constraints_request_queue",
        durable=True
    )
    response_queue = await solver_service.channel.declare_queue(
        "constraints_response_queue",
        durable=True
    )
    
    # Get and process the malformed message
    message = await queue.get(fail=False)
    if message:
        try:
            await solver_service._handle_message(message, response_queue)
        except Exception as e:
            pytest.fail(f"Worker crashed on invalid message: {e}")
        
    # 3. Publish Valid Message (to ensure worker is still alive/functional)
    # Setup Data (User & Semester)
    async with db.pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (user_internal_id, user_name, user_id, first_name, last_name, email, role)
            OVERRIDING SYSTEM VALUE
            VALUES (9003, 'test_reliable', '000099997', 'Rel', 'Able', 'rel@test.com', 'L')
            ON CONFLICT DO NOTHING
        """)
        await conn.execute("""
            INSERT INTO semesters (semester_year, semester_number, semester_start_date, semester_end_date, constraint_start_date, constraint_end_date, change_period_start, change_period_end, status)
            VALUES (9999, 3, '9999-09-01', '9999-12-01', '9999-09-01', '9999-10-01', '9999-10-01', '9999-11-01', 'SET')
            ON CONFLICT DO NOTHING
        """)
    
    msg_body = {
        "semester_year": 9999,
        "semester_number": 3,
        "new_constraint_id": 999,
        "lecturer_id": 9003
    }
    
    await channel.default_exchange.publish(
        Message(body=json.dumps(msg_body).encode(), delivery_mode=DeliveryMode.PERSISTENT),
        routing_key="constraints_request_queue"
    )
    
    # Process valid message
    message = await queue.get(fail=False)
    if message:
        await solver_service._handle_message(message, response_queue)
        # Wait for batch processing
        await asyncio.sleep(6)  # Longer than BATCH_TIMEOUT_SECONDS
    
    await solver_service.connection.close()
    await connection.close()
    
    # Verify processing happened (Schedule created)
    async with db.pool.acquire() as conn:
        sid = await conn.fetchval("SELECT schedule_id FROM schedules WHERE semester_year = 9999 AND semester_number = 3")
        assert sid is not None
    
    await db.close()
