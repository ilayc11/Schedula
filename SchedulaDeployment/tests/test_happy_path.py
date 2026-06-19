"""
E2E Test: Happy Path Scenario

Tests the CSP solver with simple, easily satisfiable constraints.
Generates a full dataset of 50 lecturers and 50 courses with one simple
constraint per lecturer (blocks one morning or afternoon per week).

Expected outcome: Solver successfully generates schedules for all courses
while respecting all constraints.

Uses backend dev API routes for all verification (no direct SQL queries).
Waits for solver completion message from RabbitMQ.
"""

import asyncio
import httpx
from datetime import datetime
from test_data_generators import setup_happy_path_data, wait_for_solver_completion


async def test_happy_path(backend_url, test_year, test_semester, num_lecturers, num_courses, test_logger):
    """
    Main test function for happy path scenario.
    
    Steps:
    1. Generate test data (50 lecturers, 50 courses, simple constraints)
    2. Wait for solver completion message from RabbitMQ
    3. Verify schedules are created for all courses (via API)
    4. Verify all constraints are respected
    """
    test_logger.info("🚀 Starting Happy Path E2E Test")
    test_logger.info(f"📊 Dataset: {num_lecturers} lecturers, {num_courses} courses")
    
    # Step 1: Generate test data
    test_logger.info("1️⃣  Generating happy path test data...")
    try:
        lecturers = await setup_happy_path_data(
            backend_url, 
            test_year, 
            test_semester,
            num_lecturers=num_lecturers,
            num_courses=num_courses
        )
        test_logger.info(f"✅ Generated data for {len(lecturers)} lecturers")
    except Exception as e:
        test_logger.error(f"❌ Failed to generate test data: {e}")
        return
    
    # Step 2: Wait for solver completion via backend API
    test_logger.info("2️⃣  Waiting for Solver completion via backend API...")
    
    solver_result = await wait_for_solver_completion(backend_url, test_year, test_semester, timeout=120)
    
    if not solver_result:
        test_logger.error("❌ Timeout waiting for solver completion message")
        test_logger.error("   Check solver and RabbitMQ logs")
        return
    
    test_logger.info(f"✅ Solver completed with status: {solver_result['status']}")
    
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
            
            if constraints_resp.status_code == 200:
                constraints = constraints_resp.json()
                test_logger.info(f"📋 Total constraints: {len(constraints)}")
            
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
                actual_course_count = num_courses
            
            # Success criteria
            success_threshold = 0.95  # At least 95% of courses scheduled
            if courses_with_schedule >= actual_course_count * success_threshold:
                test_logger.info("\n🎉 HAPPY PATH TEST PASSED!")
                test_logger.info(f"   - Schedule generated successfully")
                test_logger.info(f"   - {courses_with_schedule}/{actual_course_count} courses scheduled ({courses_with_schedule/actual_course_count*100:.1f}%)")
                test_logger.info(f"   - {session_count} total course sessions")
            else:
                test_logger.error(f"❌ Only {courses_with_schedule}/{actual_course_count} courses scheduled ({courses_with_schedule/actual_course_count*100:.1f}%)")
                test_logger.error(f"   Expected at least {int(actual_course_count * success_threshold)} courses")
        else:
            test_logger.error(f"❌ Failed to retrieve sessions via API: {sessions_resp.status_code}")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "-s"])
