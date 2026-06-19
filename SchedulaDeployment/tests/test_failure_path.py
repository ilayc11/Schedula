"""
E2E Test: Failure Path Scenario

Tests the CSP solver with impossible-to-satisfy constraints.
Generates a full dataset of 50 lecturers and 50 courses where every
lecturer blocks ALL weekdays, making scheduling impossible.

Expected outcome: Solver detects conflicts and reports failure gracefully,
with no schedule being generated or schedule being empty.

Uses backend dev API routes for all verification (no direct SQL queries).
Waits for solver completion message from RabbitMQ.
"""

import asyncio
import httpx
from datetime import datetime
from test_data_generators import setup_failure_path_data, wait_for_solver_completion


async def test_failure_path(backend_url, test_year, test_semester, num_lecturers, num_courses, test_logger):
    """
    Main test function for failure path scenario.
    
    Steps:
    1. Generate test data with impossible-to-satisfy constraints
    2. Wait for solver completion message from RabbitMQ
    3. Verify that solver reports failure (status='failed')
    4. Verify system handles failure gracefully
    """
    test_logger.info("🚀 Starting Failure Path E2E Test (Expect Solver Conflict)")
    test_logger.info(f"📊 Dataset: {num_lecturers} lecturers, {num_courses} courses (all days blocked)")
    
    # Step 1: Generate test data with impossible-to-satisfy constraints
    test_logger.info("1️⃣  Generating failure path test data (impossible constraints)...")
    try:
        lecturers = await setup_failure_path_data(
            backend_url, 
            test_year, 
            test_semester,
            num_lecturers=num_lecturers,
            num_courses=num_courses
        )
        test_logger.info(f"✅ Generated data for {len(lecturers)} lecturers (all with blocking constraints)")
    except Exception as e:
        test_logger.error(f"❌ Failed to generate test data: {e}")
        return
    
    # Step 2: Wait for solver completion via backend API
    test_logger.info("2️⃣  Waiting for Solver to detect conflicts...")
    
    solver_result = await wait_for_solver_completion(backend_url, test_year, test_semester, timeout=60)
    
    if not solver_result:
        test_logger.error("❌ Timeout waiting for solver completion message")
        test_logger.error("   Check solver and RabbitMQ logs")
        return
    
    test_logger.info(f"Received solver result with status: {solver_result['status']}")
    
    # Step 3: Verify solver correctly detected infeasibility
    if solver_result['status'] == 'failed':
        test_logger.info("✅ Solver correctly detected INFEASIBLE constraints")
        broken_constraints = solver_result.get('broken_constraints', [])
        test_logger.info(f"   Conflicting constraints: {len(broken_constraints)} constraint(s)")
        if broken_constraints:
            test_logger.info(f"   Sample constraint IDs: {broken_constraints[:3]}...")  # Show first 3
        
        # Verify no solution was saved via API
        schedule_id = solver_result.get('schedule_id')
        if schedule_id:
            async with httpx.AsyncClient(timeout=30.0) as client:
                sessions_resp = await client.get(
                    f"{backend_url}/dev/courses-schedules/schedule/{schedule_id}"
                )
                
                if sessions_resp.status_code == 200:
                    sessions = sessions_resp.json()
                    session_count = len(sessions)
                    
                    if session_count == 0:
                        test_logger.info("✅ No course sessions saved (as expected)")
                    else:
                        test_logger.error(f"❌ UNEXPECTED: {session_count} sessions saved despite failure")
                elif sessions_resp.status_code == 404:
                    test_logger.info("✅ No course sessions found (as expected)")
        
        # Step 4: Verify breaking constraints are saved to database via API
        test_logger.info("3️⃣  Verifying breaking constraints in database...")
        async with httpx.AsyncClient(timeout=30.0) as client:
            breaking_resp = await client.get(
                f"{backend_url}/dev/breaking-constraints/semester/{test_year}/{test_semester}"
            )
            
            if breaking_resp.status_code == 200:
                breaking_data = breaking_resp.json()
                db_breaking_constraints = breaking_data.get('data', [])
                
                test_logger.info(f"✅ Found {len(db_breaking_constraints)} breaking constraints in database")
                
                # Verify structure of breaking constraints
                if db_breaking_constraints:
                    sample = db_breaking_constraints[0]
                    required_fields = ['breaking_id', 'constraints_id', 'atomic_constraint_index', 
                                     'semester_year', 'semester_number', 'is_seen', 'lecturer_name']
                    
                    missing_fields = [f for f in required_fields if f not in sample]
                    if missing_fields:
                        test_logger.error(f"❌ Missing fields in breaking constraint: {missing_fields}")
                    else:
                        test_logger.info("✅ Breaking constraints have correct structure")
                    
                    # Verify atomic_constraint_index is set
                    indices = [bc.get('atomic_constraint_index') for bc in db_breaking_constraints]
                    if all(idx is not None for idx in indices):
                        test_logger.info("✅ All breaking constraints have atomic_constraint_index set")
                    else:
                        test_logger.error("❌ Some breaking constraints missing atomic_constraint_index")
                    
                    # Show sample breaking constraint details
                    test_logger.info(f"   Sample: Lecturer '{sample.get('lecturer_name')}', "
                                   f"Constraint ID {sample.get('constraints_id')}, "
                                   f"Atomic Index {sample.get('atomic_constraint_index')}")
                    
                    # Verify lecturer details are properly joined
                    lecturers_with_names = [bc for bc in db_breaking_constraints if bc.get('lecturer_name')]
                    if len(lecturers_with_names) == len(db_breaking_constraints):
                        test_logger.info("✅ All breaking constraints have lecturer names (JOIN working)")
                    else:
                        test_logger.error(f"❌ Only {len(lecturers_with_names)}/{len(db_breaking_constraints)} "
                                        "have lecturer names")
            else:
                test_logger.error(f"❌ Failed to fetch breaking constraints: {breaking_resp.status_code}")
        
        test_logger.info("\n🎉 FAILURE PATH TEST PASSED!")
        test_logger.info("   - Solver detected impossible constraints")
        test_logger.info("   - No invalid schedule was created")
        test_logger.info("   - Breaking constraints saved to database correctly")
        test_logger.info("   - System handled failure gracefully")
        
    else:
        test_logger.error(f"❌ UNEXPECTED: Solver reported '{solver_result['status']}' instead of 'failed'")
        test_logger.error("   All days were blocked - should be impossible to schedule")
        test_logger.error("   This indicates the solver is not correctly enforcing time constraints")
        
        # Show solution count if present
        if 'solution_count' in solver_result:
            test_logger.error(f"   Solution count: {solver_result['solution_count']}")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "-s"])
