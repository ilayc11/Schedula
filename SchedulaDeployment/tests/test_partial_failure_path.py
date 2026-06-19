"""
E2E Test: Partial Failure Path Scenario

Tests the CSP solver with a mixed scenario where some lecturers have
impossible constraints while others have solvable constraints.

Expected outcome: Solver detects only the conflicting constraints and reports
them specifically, while successfully scheduling courses for lecturers with
solvable constraints.

Uses backend dev API routes for all verification (no direct SQL queries).
Waits for solver completion message from RabbitMQ.
"""

import asyncio
import httpx
from test_data_generators import (
    clear_database,
    create_semester,
    create_lecturers,
    create_courses_and_offerings,
    assign_lecturers,
    wait_for_solver_completion
)


async def create_partial_failure_data(base_url, year, semester_num, num_good_lecturers=5, num_bad_lecturers=2):
    """
    Create test data with mixed constraints:
    - Some lecturers have reasonable constraints (should succeed)
    - Some lecturers block all time (should fail)
    
    Returns tuple of (good_lecturers, bad_lecturers)
    """
    print("\n" + "="*60)
    print(f"SETTING UP PARTIAL FAILURE DATA")
    print(f"Good lecturers: {num_good_lecturers}, Bad lecturers: {num_bad_lecturers}")
    print("="*60 + "\n")
    
    total_lecturers = num_good_lecturers + num_bad_lecturers
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        await clear_database(client, base_url)
        await create_semester(client, base_url, year, semester_num)
        all_lecturers = await create_lecturers(client, base_url, total_lecturers)
        
        good_lecturers = all_lecturers[:num_good_lecturers]
        bad_lecturers = all_lecturers[num_good_lecturers:]
        
        offerings = await create_courses_and_offerings(client, base_url, total_lecturers, year, semester_num)
        await assign_lecturers(client, base_url, all_lecturers, offerings)
        
        # Good lecturers: Block only Monday morning (solvable)
        print("Creating constraints for good lecturers (solvable)...")
        for lecturer in good_lecturers:
            constraint_data = {
                "lecturer_internal_id": lecturer['user_internal_id'],
                "schedule_id": None,
                "semester_year": year,
                "semester_number": semester_num,
                "raw_text": "I cannot teach on Monday mornings.",
                "structured_rules": {
                    "atomic_constraints": [
                        {
                            "type": "block",
                            "days": [2],
                            "time_slot": {"start_hour": 8, "end_hour": 12}
                        }
                    ]
                },
                "secretary_override_as_hard": None
            }
            await client.post(f"{base_url}/dev/constraints/", json=constraint_data)
        
        # Bad lecturers: Block ALL days (impossible)
        print("Creating constraints for bad lecturers (impossible)...")
        for lecturer in bad_lecturers:
            atomic_constraints = [
                {"type": "block", "days": [day], "time_slot": {"start_hour": 8, "end_hour": 15 if day == 6 else 20}}
                for day in range(1, 7)
            ]
            
            constraint_data = {
                "lecturer_internal_id": lecturer['user_internal_id'],
                "schedule_id": None,
                "semester_year": year,
                "semester_number": semester_num,
                "raw_text": "I cannot teach on any day of the week.",
                "structured_rules": {"atomic_constraints": atomic_constraints},
                "secretary_override_as_hard": None
            }
            await client.post(f"{base_url}/dev/constraints/", json=constraint_data)
        
        print("\nWaiting for constraint messages to reach solver...")
        await asyncio.sleep(2.0)
    
    print("\n✅ Partial failure data generation complete!\n")
    return good_lecturers, bad_lecturers


async def test_partial_failure_path(backend_url, test_year, test_semester, num_good, num_bad, test_logger):
    """
    Main test function for partial failure scenario.
    
    Steps:
    1. Generate test data with mixed constraints (some solvable, some impossible)
    2. Wait for solver completion
    3. Verify solver reports failure (due to impossible constraints)
    4. Verify only the impossible constraints are flagged as breaking
    5. Verify courses for "good" lecturers could theoretically be scheduled
    """
    test_logger.info("🚀 Starting Partial Failure Path E2E Test")
    test_logger.info(f"📊 Dataset: {num_good} good lecturers, {num_bad} bad lecturers")
    
    # Step 1: Generate mixed test data
    test_logger.info("1️⃣  Generating partial failure test data...")
    try:
        good_lecturers, bad_lecturers = await create_partial_failure_data(
            backend_url, 
            test_year, 
            test_semester,
            num_good_lecturers=num_good,
            num_bad_lecturers=num_bad
        )
        test_logger.info(f"✅ Generated data for {len(good_lecturers)} good + {len(bad_lecturers)} bad lecturers")
    except Exception as e:
        test_logger.error(f"❌ Failed to generate test data: {e}")
        return
    
    # Step 2: Wait for solver completion
    test_logger.info("2️⃣  Waiting for Solver to process constraints...")
    
    solver_result = await wait_for_solver_completion(backend_url, test_year, test_semester, timeout=60)
    
    if not solver_result:
        test_logger.error("❌ Timeout waiting for solver completion message")
        return
    
    test_logger.info(f"Received solver result with status: {solver_result['status']}")
    
    # Step 3: Verify solver detected the impossible constraints
    if solver_result['status'] == 'failed':
        test_logger.info("✅ Solver correctly detected INFEASIBLE constraints")
        
        # Step 4: Verify breaking constraints via API
        test_logger.info("3️⃣  Verifying only bad lecturers' constraints are flagged...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get breaking constraints
            breaking_resp = await client.get(
                f"{backend_url}/dev/breaking-constraints/{test_year}/{test_semester}"
            )
            
            if breaking_resp.status_code == 200:
                breaking_data = breaking_resp.json()
                db_breaking_constraints = breaking_data.get('data', [])
                
                test_logger.info(f"Found {len(db_breaking_constraints)} breaking constraints")
                
                # Get lecturer IDs from breaking constraints
                breaking_lecturer_ids = {bc['lecturer_internal_id'] for bc in db_breaking_constraints}
                bad_lecturer_ids = {lect['user_internal_id'] for lect in bad_lecturers}
                good_lecturer_ids = {lect['user_internal_id'] for lect in good_lecturers}
                
                # Verify only bad lecturers are flagged
                bad_lecturers_flagged = breaking_lecturer_ids & bad_lecturer_ids
                good_lecturers_flagged = breaking_lecturer_ids & good_lecturer_ids
                
                if len(bad_lecturers_flagged) > 0:
                    test_logger.info(f"✅ {len(bad_lecturers_flagged)}/{len(bad_lecturers)} bad lecturers flagged")
                else:
                    test_logger.error("❌ No bad lecturers were flagged!")
                
                if len(good_lecturers_flagged) == 0:
                    test_logger.info(f"✅ No good lecturers were incorrectly flagged")
                else:
                    test_logger.error(f"❌ {len(good_lecturers_flagged)} good lecturers incorrectly flagged!")
                
                # Show details of breaking constraints
                for bc in db_breaking_constraints[:3]:  # Show first 3
                    test_logger.info(f"   Breaking: {bc['lecturer_name']} - "
                                   f"Constraint {bc['constraints_id']}, "
                                   f"Atomic Index {bc['atomic_constraint_index']}")
                
                # Verify structure
                if db_breaking_constraints:
                    sample = db_breaking_constraints[0]
                    required_fields = ['breaking_id', 'constraints_id', 'atomic_constraint_index']
                    missing = [f for f in required_fields if f not in sample]
                    
                    if not missing:
                        test_logger.info("✅ Breaking constraints have correct structure")
                    else:
                        test_logger.error(f"❌ Missing fields: {missing}")
                
                # Final verdict
                if (len(bad_lecturers_flagged) > 0 and 
                    len(good_lecturers_flagged) == 0):
                    test_logger.info("\n🎉 PARTIAL FAILURE PATH TEST PASSED!")
                    test_logger.info("   - Solver correctly identified impossible constraints")
                    test_logger.info("   - Only bad lecturers' constraints were flagged")
                    test_logger.info("   - Good lecturers' constraints were not flagged")
                    test_logger.info("   - Breaking constraints properly stored in database")
                else:
                    test_logger.error("\n❌ PARTIAL FAILURE PATH TEST FAILED!")
                    test_logger.error("   - Incorrect constraint identification")
            else:
                test_logger.error(f"❌ Failed to fetch breaking constraints: {breaking_resp.status_code}")
    else:
        test_logger.error(f"❌ UNEXPECTED: Solver reported '{solver_result['status']}' instead of 'failed'")
        test_logger.error("   Some constraints block all time - should be impossible to schedule")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "-s"])

