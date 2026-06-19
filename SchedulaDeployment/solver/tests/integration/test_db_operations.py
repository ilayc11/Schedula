"""
Integration tests for database operations.

Tests Database class methods for constraints, solutions, and breaking constraints.
"""
import pytest
import asyncpg
import json
from src.db import Database
from src.solver import CSPSolver
from datetime import time


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fetch_constraints(db_instance, setup_db_data, mock_atomic_constraint_factory):
    """Integration: Insert via SQL, Fetch via DB class."""
    
    # 1. Insert Raw Constraint via SQL
    rule = mock_atomic_constraint_factory(days=[2], start_hour=10, end_hour=12)
    structured_dict = {"atomic_constraints": [rule]}
    
    async with db_instance.pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO lecturer_constraints 
            (lecturer_internal_id, semester_year, semester_number, raw_text, structured_rules)
            VALUES (9001, 9999, 1, 'Test Integ', $1)
        """, json.dumps(structured_dict))

    # 2. Fetch using class method
    constraints = await db_instance.get_all_constraints_by_semester(9999, 1)
    
    # 3. Verify
    assert len(constraints) == 1
    assert constraints[0]['lecturer_internal_id'] == 9001
    
    # Check structured_rules is already a dict
    fetched_rules = constraints[0]['structured_rules']
    assert fetched_rules['atomic_constraints'][0]['days'] == [2]


@pytest.mark.integration
@pytest.mark.asyncio
async def test_save_solution(db_instance, setup_db_data):
    """Integration: Save solution to DB."""
    
    # 1. Create Draft Schedule
    schedule_id = await db_instance.get_or_create_draft_schedule(9999, 1)
    assert schedule_id is not None
    
    # 2. Save Mock Solution
    sessions = [
        {
            "offering_id": 1,
            "lecturer_id": 9001,
            "day_of_week": 1,
            "start_time": time(9, 0),
            "end_time": time(11, 0)
        }
    ]
    
    # We need a valid offering_id. Let's create one if FKs are enforced.
    async with db_instance.pool.acquire() as conn:
        # Create course
        course_id = await conn.fetchval("""
            INSERT INTO courses (department_id, degree_level, course_number, course_name, credit_points)
            VALUES (1, 1, 99999, 'Test Course', 3.0)
            ON CONFLICT (course_number) DO UPDATE SET course_name = EXCLUDED.course_name
            RETURNING course_id
        """)
        
        # Create offering
        offering_id = await conn.fetchval("""
            INSERT INTO course_offering (course_number, academic_year, semester, group_number)
            VALUES (99999, 9999, 1, 1)
            ON CONFLICT (course_number, academic_year, semester, group_number) 
            DO UPDATE SET group_number = EXCLUDED.group_number
            RETURNING offering_id
        """)
        
        # Add cohort for the offering
        await conn.execute("""
            INSERT INTO offering_cohorts (offering_id, target_department_id, target_year_level)
            VALUES ($1, 1, 1)
            ON CONFLICT (offering_id, target_department_id, target_year_level) DO NOTHING
        """, offering_id)
        
        sessions[0]['offering_id'] = offering_id

    await db_instance.save_solution(schedule_id, sessions)
    
    # 3. Verify
    async with db_instance.pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM courses_schedules WHERE schedule_id = $1", schedule_id)
        assert count == 1


@pytest.mark.integration
@pytest.mark.asyncio
async def test_save_breaking_constraints(db_instance, setup_db_data, mock_atomic_constraint_factory):
    """Integration: Save breaking constraints to DB."""
    
    # 1. Create a constraint in the database first
    rule = mock_atomic_constraint_factory(days=[2], start_hour=10, end_hour=12)
    structured_dict = {"atomic_constraints": [rule]}
    
    async with db_instance.pool.acquire() as conn:
        constraint_id = await conn.fetchval("""
            INSERT INTO lecturer_constraints 
            (lecturer_internal_id, semester_year, semester_number, raw_text, structured_rules)
            VALUES (9001, 9999, 1, 'Test Breaking Constraint', $1)
            RETURNING constraints_id
        """, json.dumps(structured_dict))
    
    # 2. Save breaking constraints
    breaking_constraints = [
        {
            "constraints_id": constraint_id,
            "atomic_index": 0
        }
    ]
    
    count = await db_instance.save_breaking_constraints(9999, 1, breaking_constraints)
    
    # 3. Verify
    assert count == 1
    
    async with db_instance.pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT * FROM breaking_constraints 
            WHERE semester_year = 9999 AND semester_number = 1
        """)
        assert len(rows) == 1
        assert rows[0]['constraints_id'] == constraint_id
        
        # Verify breaking_atomic_constraints is a JSONB array with the right structure
        breaking_atomics = rows[0]['breaking_atomic_constraints']
        if isinstance(breaking_atomics, str):
            breaking_atomics = json.loads(breaking_atomics)
        
        assert isinstance(breaking_atomics, list)
        assert len(breaking_atomics) == 1
        assert breaking_atomics[0]['atomic_constraint_index'] == 0
        assert breaking_atomics[0]['days'] == [2]
        assert rows[0]['is_seen'] == False


@pytest.mark.integration
@pytest.mark.asyncio
async def test_clear_breaking_constraints(db_instance, setup_db_data, mock_atomic_constraint_factory):
    """Integration: Clear breaking constraints before re-solving."""
    
    # 1. Create a constraint with TWO atomic constraints
    rule1 = mock_atomic_constraint_factory(days=[2], start_hour=10, end_hour=12)
    rule2 = mock_atomic_constraint_factory(days=[3], start_hour=14, end_hour=16)
    structured_dict = {"atomic_constraints": [rule1, rule2]}
    
    async with db_instance.pool.acquire() as conn:
        constraint_id = await conn.fetchval("""
            INSERT INTO lecturer_constraints 
            (lecturer_internal_id, semester_year, semester_number, raw_text, structured_rules)
            VALUES (9001, 9999, 1, 'Test Clear Breaking', $1)
            RETURNING constraints_id
        """, json.dumps(structured_dict))
    
    # 2. Save some breaking constraints (they'll be grouped by constraints_id)
    breaking_constraints = [
        {"constraints_id": constraint_id, "atomic_index": 0},
        {"constraints_id": constraint_id, "atomic_index": 1}
    ]
    
    await db_instance.save_breaking_constraints(9999, 1, breaking_constraints)
    
    # 3. Verify they exist as 1 group (grouped by constraints_id)
    async with db_instance.pool.acquire() as conn:
        count_before = await conn.fetchval("""
            SELECT COUNT(*) FROM breaking_constraints 
            WHERE semester_year = 9999 AND semester_number = 1
        """)
        assert count_before == 1
        
        # Verify the group contains both atomic constraints
        row = await conn.fetchrow("""
            SELECT breaking_atomic_constraints FROM breaking_constraints 
            WHERE semester_year = 9999 AND semester_number = 1
        """)
        breaking_atomics = row['breaking_atomic_constraints']
        if isinstance(breaking_atomics, str):
            breaking_atomics = json.loads(breaking_atomics)
        assert len(breaking_atomics) == 2
    
    # 4. Clear breaking constraints
    cleared_count = await db_instance.clear_breaking_constraints(9999, 1)
    assert cleared_count == 1
    
    # 5. Verify they're gone
    async with db_instance.pool.acquire() as conn:
        count_after = await conn.fetchval("""
            SELECT COUNT(*) FROM breaking_constraints 
            WHERE semester_year = 9999 AND semester_number = 1
        """)
        assert count_after == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_save_multiple_breaking_constraints(db_instance, setup_db_data, mock_atomic_constraint_factory):
    """Integration: Save breaking constraints from multiple lecturers."""
    
    # 1. Create constraints for two lecturers
    async with db_instance.pool.acquire() as conn:
        # Create second test user
        await conn.execute("""
            INSERT INTO users (user_internal_id, user_name, user_id, first_name, last_name, email, role)
            OVERRIDING SYSTEM VALUE
            VALUES (9002, 'test_integ2', '000099998', 'Integ2', 'User2', 'integ2@test.com', 'L')
            ON CONFLICT (user_internal_id) DO NOTHING
        """)
        
        # Create constraints for both lecturers
        rule1 = mock_atomic_constraint_factory(days=[2], start_hour=10, end_hour=12)
        rule2 = mock_atomic_constraint_factory(days=[3], start_hour=14, end_hour=16)
        
        constraint_id_1 = await conn.fetchval("""
            INSERT INTO lecturer_constraints 
            (lecturer_internal_id, semester_year, semester_number, raw_text, structured_rules)
            VALUES (9001, 9999, 1, 'Lecturer 1 Constraint', $1)
            RETURNING constraints_id
        """, json.dumps({"atomic_constraints": [rule1]}))
        
        constraint_id_2 = await conn.fetchval("""
            INSERT INTO lecturer_constraints 
            (lecturer_internal_id, semester_year, semester_number, raw_text, structured_rules)
            VALUES (9002, 9999, 1, 'Lecturer 2 Constraint', $1)
            RETURNING constraints_id
        """, json.dumps({"atomic_constraints": [rule2]}))
    
    # 2. Save breaking constraints from both
    breaking_constraints = [
        {"constraints_id": constraint_id_1, "atomic_index": 0},
        {"constraints_id": constraint_id_2, "atomic_index": 0}
    ]
    
    count = await db_instance.save_breaking_constraints(9999, 1, breaking_constraints)
    assert count == 2  # Two groups (one per constraints_id)
    
    # 3. Verify both are saved
    async with db_instance.pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT bc.*, lc.lecturer_internal_id 
            FROM breaking_constraints bc
            JOIN lecturer_constraints lc ON bc.constraints_id = lc.constraints_id
            WHERE bc.semester_year = 9999 AND bc.semester_number = 1
            ORDER BY lc.lecturer_internal_id
        """)
        assert len(rows) == 2  # Two groups, one per constraint
        assert rows[0]['lecturer_internal_id'] == 9001
        assert rows[1]['lecturer_internal_id'] == 9002
        
        # Verify each group has one atomic constraint
        for row in rows:
            breaking_atomics = row['breaking_atomic_constraints']
            if isinstance(breaking_atomics, str):
                breaking_atomics = json.loads(breaking_atomics)
            assert len(breaking_atomics) == 1
            assert breaking_atomics[0]['atomic_constraint_index'] == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_multiple_semesters_isolation(db_instance, setup_db_data):
    """
    Integration: Ensure solver/DB logic handles multiple semesters independently.
    """
    
    # Setup: Insert Semester 2
    async with db_instance.pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO semesters (
                semester_year, semester_number, 
                semester_start_date, semester_end_date, 
                constraint_start_date, constraint_end_date, 
                change_period_start, change_period_end, 
                status
            ) VALUES (
                9999, 2, 
                '9999-05-01', '9999-08-01', 
                '9999-05-01', '9999-06-01', 
                '9999-06-01', '9999-07-01', 
                'SET'
            ) ON CONFLICT DO NOTHING
        """)
        
        # Insert Constraint for Sem 1
        await conn.execute("""
            INSERT INTO lecturer_constraints 
            (lecturer_internal_id, semester_year, semester_number, raw_text, structured_rules)
            VALUES (9001, 9999, 1, 'Sem 1', '{}')
        """)
        
        # Insert Constraint for Sem 2
        await conn.execute("""
            INSERT INTO lecturer_constraints 
            (lecturer_internal_id, semester_year, semester_number, raw_text, structured_rules)
            VALUES (9001, 9999, 2, 'Sem 2', '{}')
        """)

    # Test Fetch Sem 1
    constraints_1 = await db_instance.get_all_constraints_by_semester(9999, 1)
    assert len(constraints_1) == 1
    
    # Test Fetch Sem 2
    constraints_2 = await db_instance.get_all_constraints_by_semester(9999, 2)
    assert len(constraints_2) == 1
    
    # Test Solve & Save Sem 1
    sid_1 = await db_instance.get_or_create_draft_schedule(9999, 1)
    await db_instance.save_solution(sid_1, [])
    
    # Test Solve & Save Sem 2
    sid_2 = await db_instance.get_or_create_draft_schedule(9999, 2)
    assert sid_1 != sid_2
    await db_instance.save_solution(sid_2, [])
    
    # Verify separation
    async with db_instance.pool.acquire() as conn:
        count_1 = await conn.fetchval("SELECT COUNT(*) FROM schedules WHERE schedule_id = $1", sid_1)
        count_2 = await conn.fetchval("SELECT COUNT(*) FROM schedules WHERE schedule_id = $1", sid_2)
        assert count_1 == 1
        assert count_2 == 1

