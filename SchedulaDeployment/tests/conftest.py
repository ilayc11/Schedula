"""
Pytest configuration for root-level E2E tests.

These tests use the backend HTTP API and don't directly interact with RabbitMQ,
but we still need to purge queues before tests to avoid processing leftover messages.
"""
import pytest
import asyncio
import os
import logging

# Suppress verbose HTTP client logging
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


# Test configuration constants
BACKEND_URL = "http://localhost:8000"
TEST_YEAR = 2025
TEST_SEMESTER = 1
NUM_LECTURERS = 50
NUM_COURSES = 50


@pytest.fixture(scope="session")
def backend_url():
    """Backend API URL for tests."""
    return os.getenv("BACKEND_URL", BACKEND_URL)


@pytest.fixture(scope="session")
def test_year():
    """Test semester year."""
    return TEST_YEAR


@pytest.fixture(scope="session")
def test_semester():
    """Test semester number."""
    return TEST_SEMESTER


@pytest.fixture(scope="session")
def num_lecturers():
    """Number of lecturers to create in tests."""
    return NUM_LECTURERS


@pytest.fixture(scope="session")
def num_courses():
    """Number of courses to create in tests."""
    return NUM_COURSES


@pytest.fixture(scope="session")
def num_good():
    """Number of good lecturers (solvable constraints) for partial failure test."""
    return 5


@pytest.fixture(scope="session")
def num_bad():
    """Number of bad lecturers (impossible constraints) for partial failure test."""
    return 2


@pytest.fixture(scope="session")
def rabbitmq_url():
    """RabbitMQ connection URL for queue management."""
    return os.getenv("RABBITMQ_URL", "amqp://rabbitmq:rabbitmq@localhost:5672/")


@pytest.fixture(scope="function")
def test_logger(request):
    """
    Create a logger for each test with the test name.
    
    Usage:
        async def test_something(test_logger):
            test_logger.info("Message")
    """
    logger_name = request.node.name
    logger = logging.getLogger(logger_name)
    
    # Configure logging if not already configured
    if not logger.handlers:
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
    
    return logger


@pytest.fixture(scope="function", autouse=False)
async def ensure_queues_drained_between_tests(rabbitmq_url):
    """
    Ensure all RabbitMQ messages are processed between tests.
    
    This runs AFTER each test to ensure that before the next test starts
    (and clears the database), all pending solver messages have been fully
    processed. This prevents foreign key violations from orphaned messages.
    
    Uses autouse=True to run automatically after every test.
    """
    # Run before test - nothing to do
    yield
    
    # Run after test - ensure all messages are drained
    from aio_pika import connect
    import asyncio
    import sys
    
    SOLVER_BATCH_TIMEOUT = 1.5
    SOLVER_MAX_BATCH_WAIT = 3.0
    MAX_DRAIN_TIME = 30.0  # Maximum time to wait for queue to drain
    CHECK_INTERVAL = 0.5   # How often to check queue depth
    
    try:
        connection = await connect(rabbitmq_url)
        channel = await connection.channel()
        
        # Declare queue to check its status
        request_queue = await channel.declare_queue("constraints_request_queue", durable=True)
        
        start_time = asyncio.get_event_loop().time()
        consecutive_empty_checks = 0
        REQUIRED_EMPTY_CHECKS = 2  # Queue must be empty for this many checks
        showed_drain_msg = False
        
        while True:
            # Get current message count - re-declare with passive to get current state
            queue_info = await request_queue.channel.declare_queue(
                "constraints_request_queue", 
                durable=True, 
                passive=True
            )
            message_count = queue_info.declaration_result.message_count
            
            if message_count == 0:
                consecutive_empty_checks += 1
                
                if consecutive_empty_checks == 1:
                    # First time we see empty queue, wait for batch completion
                    if not showed_drain_msg:
                        print(f"\n🔄 Draining queues (waiting {SOLVER_BATCH_TIMEOUT + SOLVER_MAX_BATCH_WAIT:.0f}s)...", end='', flush=True)
                        showed_drain_msg = True
                    await asyncio.sleep(SOLVER_BATCH_TIMEOUT + SOLVER_MAX_BATCH_WAIT)
                elif consecutive_empty_checks >= REQUIRED_EMPTY_CHECKS:
                    # Queue stayed empty, we're done
                    if showed_drain_msg:
                        print(" ✓")
                    break
                else:
                    # Check again to confirm
                    await asyncio.sleep(CHECK_INTERVAL)
            else:
                # Queue has messages, reset counter
                consecutive_empty_checks = 0
                elapsed = asyncio.get_event_loop().time() - start_time
                
                if not showed_drain_msg:
                    print(f"\n🔄 Draining {message_count} messages...", end='', flush=True)
                    showed_drain_msg = True
                elif message_count > 0 and int(elapsed) % 5 == 0:  # Update every 5 seconds
                    print(f" ({message_count} left)", end='', flush=True)
                
                if elapsed > MAX_DRAIN_TIME:
                    print(f"\n⚠ Timeout after {MAX_DRAIN_TIME}s, purging {message_count} messages...")
                    purged = await request_queue.purge()
                    print(f"✓ Purged {purged} messages")
                    break
                
                await asyncio.sleep(CHECK_INTERVAL)
        
        await connection.close()
        
    except Exception as e:
        print(f"\n⚠ Queue drain error: {e}")


@pytest.fixture(scope="session", autouse=True)
async def purge_rabbitmq_queues_once(rabbitmq_url):
    """
    Purge RabbitMQ queues once at the start of the test session.
    
    This clears any leftover messages from previous test runs.
    Between tests, the function-scoped fixture handles draining.
    
    Uses autouse=True so it runs automatically before any tests.
    """
    from aio_pika import connect
    
    try:
        connection = await connect(rabbitmq_url)
        channel = await connection.channel()
        
        # Purge both queues
        total_purged = 0
        for queue_name in ["constraints_request_queue", "constraints_response_queue"]:
            try:
                queue = await channel.declare_queue(queue_name, durable=True)
                purged_count = await queue.purge()
                total_purged += purged_count
            except Exception:
                pass
        
        await connection.close()
        if total_purged > 0:
            print(f"✓ Purged {total_purged} old messages\n")
    except Exception:
        pass  # Silently continue if RabbitMQ not available yet
    
    yield
