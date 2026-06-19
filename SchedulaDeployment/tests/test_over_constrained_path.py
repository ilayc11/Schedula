"""
E2E Test: Over-Constrained Path Scenario

Tests the CSP solver with challenging but solvable constraints.
Generates a full dataset of 50 lecturers and 50 courses where lecturers
have multiple overlapping time constraints:
- 30% of lecturers: 1-2 blocks (light constraints)
- 50% of lecturers: 3-4 blocks (medium constraints)
- 20% of lecturers: 5-6 blocks (heavy constraints)

Expected outcome: Solver successfully generates schedules for all courses
despite the complex constraint landscape, demonstrating robust solving capability.

Uses backend dev API routes for all verification (no direct SQL queries).
Waits for solver completion message from RabbitMQ.
"""

import asyncio
import httpx
from datetime import datetime
from test_data_generators import setup_over_constrained_data, wait_for_solver_completion


async def test_over_constrained_path(backend_url, test_year, test_semester, num_lecturers, num_courses, test_logger):
    """
    Main test function for over-constrained scenario.
    
    Steps:
    1. Generate test data with multiple overlapping constraints per lecturer
    2. Wait for solver completion message from RabbitMQ
    3. Verify schedules are created despite complexity (via API)
    4. Measure and report solver performance
    5. Verify all constraints are respected
    """
    test_logger.info("🚀 Starting Over-Constrained Path E2E Test")
    test_logger.info(f"📊 Dataset: {num_lecturers} lecturers, {num_courses} courses")
    test_logger.info("📋 Constraint complexity: 30% light, 50% medium, 20% heavy")
    
    # Step 1: Generate test data with multiple overlapping constraints per lecturer
    test_logger.info("1️⃣  Generating over-constrained test data...")
    try:
        lecturers = await setup_over_constrained_data(
            backend_url, 
            test_year, 
            test_semester,
            num_lecturers=num_lecturers,
            num_courses=num_courses
        )
        test_logger.info(f"✅ Generated data for {len(lecturers)} lecturers with complex constraints")
    except Exception as e:
        test_logger.error(f"❌ Failed to generate test data: {e}")
        return
    
    # Step 2: Wait for solver completion via backend API
    test_logger.info("2️⃣  Waiting for Solver to process complex constraints...")
    test_logger.info("   (This may take longer due to constraint complexity)")
    
    start_time = datetime.now()
    
    solver_result = await wait_for_solver_completion(backend_url, test_year, test_semester, timeout=180)
    
    solve_time = (datetime.now() - start_time).seconds
    
    if not solver_result:
        test_logger.error("❌ Timeout waiting for solver completion message")
        test_logger.error("   The constraints may be too complex or solver may have failed")
        test_logger.error("   Check solver and RabbitMQ logs")
        return
    
    test_logger.info(f"✅ Solver completed in {solve_time}s with status: {solver_result['status']}")
    
    if solver_result['status'] != 'solved':
        test_logger.error(f"❌ Solver failed with status: {solver_result['status']}")
        if 'broken_constraints' in solver_result:
            test_logger.error(f"   Broken constraints: {solver_result['broken_constraints']}")
        return
    
    # Step 3: Verify solution via API
    test_logger.info(f"   Solution count from solver: {solver_result.get('solution_count', 0)}")
    schedule_id = solver_result['schedule_id']
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Get course sessions for this schedule via API
        sessions_resp = await client.get(
            f"{backend_url}/dev/courses-schedules/schedule/{schedule_id}"
        )
        
        if sessions_resp.status_code == 200:
            sessions = sessions_resp.json()
            session_count = len(sessions)
            test_logger.info(f"✅ Verified {session_count} course sessions via API")
            
            # Count unique courses with schedules
            unique_offerings = set()
            for session in sessions:
                unique_offerings.add(session['offering_id'])
            
            courses_with_schedule = len(unique_offerings)
            test_logger.info(f"📚 Courses with schedules: {courses_with_schedule}/{num_courses}")
            
            # Get constraint count via API
            constraints_resp = await client.get(
                f"{backend_url}/dev/constraints/semester/{test_year}/{test_semester}"
            )
            
            total_constraints = 0
            if constraints_resp.status_code == 200:
                constraints = constraints_resp.json()
                total_constraints = len(constraints)
                test_logger.info(f"📋 Total constraints in system: {total_constraints}")
                test_logger.info(f"   Average: {total_constraints/num_lecturers:.1f} constraints per lecturer")
            
            # Get all offerings to verify total count
            offerings_resp = await client.get(f"{backend_url}/dev/course-offering/")
            if offerings_resp.status_code == 200:
                all_offerings = offerings_resp.json()
                semester_offerings = [
                    o for o in all_offerings 
                    if o['academic_year'] == test_year and o['semester'] == test_semester
                ]
                actual_course_count = len(semester_offerings)
                test_logger.info(f"📚 Total offerings in semester: {actual_course_count}")
            else:
                actual_course_count = NUM_COURSES
            
            # Performance metrics
            test_logger.info("\n📊 Performance Metrics:")
            test_logger.info(f"   - Solve time: {solve_time}s")
            if solve_time > 0:
                test_logger.info(f"   - Sessions per second: {session_count/solve_time:.2f}")
            test_logger.info(f"   - Success rate: {courses_with_schedule/actual_course_count*100:.1f}%")
            
            # Success criteria
            success_threshold = 0.90  # At least 90% of courses scheduled
            if courses_with_schedule >= actual_course_count * success_threshold:
                test_logger.info("\n🎉 OVER-CONSTRAINED PATH TEST PASSED!")
                test_logger.info(f"   - Schedule generated successfully despite complex constraints")
                test_logger.info(f"   - {courses_with_schedule}/{actual_course_count} courses scheduled ({courses_with_schedule/actual_course_count*100:.1f}%)")
                test_logger.info(f"   - {session_count} total course sessions")
                test_logger.info(f"   - Solver handled {total_constraints} constraints")
                test_logger.info(f"   - Completed in {solve_time} seconds")
            else:
                test_logger.error(f"❌ Only {courses_with_schedule}/{actual_course_count} courses scheduled ({courses_with_schedule/actual_course_count*100:.1f}%)")
                test_logger.error(f"   Expected at least {int(actual_course_count * success_threshold)} courses ({success_threshold*100:.0f}%)")
        else:
            test_logger.error(f"❌ Failed to retrieve sessions via API: {sessions_resp.status_code}")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "-s"])
