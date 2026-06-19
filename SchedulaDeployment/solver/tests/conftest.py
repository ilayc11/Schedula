"""
Pytest configuration and fixtures for solver tests.

Provides shared test fixtures for unit, integration, and load tests.
"""
import pytest
import os
import json
import asyncio
import uuid
import asyncpg
from typing import Dict, Any, List
from datetime import datetime
from src.db import Database


# Configure pytest markers
def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers", "unit: Unit tests (fast, no external dependencies)"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests (requires DB and RabbitMQ)"
    )
    config.addinivalue_line(
        "markers", "load: Load and performance tests (slow)"
    )


# --- Mock Factories ---

@pytest.fixture
def mock_atomic_constraint_factory():
    """Factory to create valid atomic constraints resembling backend output."""
    def _create(
        constraint_id: str = None,
        days: List[int] = None,
        start_hour: int = 9,
        end_hour: int = 12,
        priority: str = "hard",
        ctype: str = "block"
    ) -> Dict[str, Any]:
        if not constraint_id:
            constraint_id = f"test_{uuid.uuid4()}"
        if days is None:
            days = [1]  # Sunday (1-indexed, matching DB convention)
            
        # Solver expects start_hour/end_hour as integers, not time strings
        return {
            "type": ctype,
            "days": days,
            "time_slot": {
                "start_hour": start_hour,
                "end_hour": end_hour
            }
        }
    return _create

@pytest.fixture
def mock_db_constraint_row_factory(mock_atomic_constraint_factory):
    """Factory to create DB row-like dictionaries matching LLM pipeline output format."""
    def _create(
        lecturer_id: int = 101, 
        constraints_id: int = 1,
        atomic_constraints: List[Dict[str, Any]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        # If no atomic_constraints provided, create one using kwargs
        if atomic_constraints is None:
            rule = mock_atomic_constraint_factory(**kwargs)
            atomic_constraints = [rule]
        
        # Solver expects: structured_rules = {"atomic_constraints": [...]}
        # This matches the LLM pipeline output format
        return {
            "constraints_id": constraints_id,
            "lecturer_internal_id": lecturer_id,
            "structured_rules": {
                "atomic_constraints": atomic_constraints
            }
        }
    return _create

# --- Shared Fixtures ---

@pytest.fixture(scope="session")
def rabbitmq_url():
    # Default to localhost for local testing
    return os.getenv("RABBITMQ_URL", "amqp://rabbitmq:rabbitmq@localhost:5672/")

@pytest.fixture(scope="session")
def database_url():
    return os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/schedula")

@pytest.fixture
async def purge_rabbitmq_queues(rabbitmq_url):
    """Fixture to purge RabbitMQ queues before each test that uses RabbitMQ."""
    from aio_pika import connect
    
    connection = await connect(rabbitmq_url)
    channel = await connection.channel()
    
    # Purge both queues
    for queue_name in ["constraints_request_queue", "constraints_response_queue"]:
        try:
            queue = await channel.declare_queue(queue_name, durable=True)
            await queue.purge()
        except Exception as e:
            print(f"Warning: Could not purge queue {queue_name}: {e}")
    
    await connection.close()
    yield

@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

# --- DB Fixtures (Global) ---

# Global flag to ensure schema is initialized only once per session
_schema_initialized = False

@pytest.fixture
async def db_instance(database_url):
    """Fixture for Database instance connected to test DB."""
    global _schema_initialized
    db = Database()
    db.url = database_url 
    await db.connect()
    
    if not _schema_initialized:
        # Initialize Schema
        # We need to find init_db.sql relative to this file
        # Assuming test is run from SchedulaDeployment/solver/tests/.. or root
        # File is at ../../../SchedulaBackend/src/database/init_db.sql from here?
        # Correct path from workspace root: SchedulaBackend/src/database/init_db.sql
        
        # Try finding it relative to workspace root
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
        init_sql_path = os.path.join(base_path, "SchedulaBackend/src/database/init_db.sql")
        
        if os.path.exists(init_sql_path):
            with open(init_sql_path, "r") as f:
                sql_script = f.read()
                async with db.pool.acquire() as conn:
                    # Wipe first to be clean
                    await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
                    await conn.execute(sql_script)
        else:
            # Fallback or error
            print(f"WARNING: init_db.sql not found at {init_sql_path}")
            
        _schema_initialized = True

    yield db
    await db.close()

@pytest.fixture
async def setup_db_data(db_instance):
    """Clean and setup basic DB data."""
    # Clean tables
    async with db_instance.pool.acquire() as conn:
        await conn.execute("DELETE FROM lecturer_constraints WHERE semester_year = 9999")
        await conn.execute("DELETE FROM schedules WHERE semester_year = 9999")
        await conn.execute("DELETE FROM users WHERE user_internal_id >= 9000")
        
        # Insert Test User
        await conn.execute("""
            INSERT INTO users (user_internal_id, user_name, user_id, first_name, last_name, email, role)
            OVERRIDING SYSTEM VALUE
            VALUES (9001, 'test_integ', '000099999', 'Integ', 'User', 'integ@test.com', 'L')
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
