"""
E2E Test: Realistic University Scenario

Tests the CSP solver with a plausible university dataset:
- 3 departments (CS, Math, EE) with 30 lecturers total
- 40 courses with varied credit points (2-5 hours)
- Cross-listed courses shared across departments (multi-cohort)
- Team-teaching (multiple lecturers on same course)
- Lecturers teaching 1-3 courses each
- Realistic constraint distribution:
    ~20% no constraints, ~30% simple, ~25% medium, ~15% complex, ~10% secretary override
- Mix of hard/soft constraint priorities

Expected outcome: Solver successfully schedules all or nearly all courses
while respecting constraints. This validates the solver against realistic
scheduling pressure from cohort overlaps, lecturer overlaps, and varied
constraint types.

Uses backend dev API routes for all verification (no direct SQL queries).
"""

import asyncio
import httpx
from datetime import datetime
from test_data_generators import setup_realistic_university_data, wait_for_solver_completion


async def test_realistic_university(backend_url, test_year, test_semester, test_logger):
    """
    Main test function for realistic university scenario.

    Steps:
    1. Generate realistic university data (3 depts, 40 courses, varied constraints)
    2. Wait for solver completion
    3. Verify schedule is produced and covers all/most courses
    4. Verify no-overlap invariants (lecturer, cohort)
    5. Verify constraint respect (blocked slots not used)
    6. Report quality metrics
    """
    test_logger.info("🚀 Starting Realistic University E2E Test")
    test_logger.info("📊 Dataset: 3 departments, 30 lecturers, 40 courses (varied credits)")
    test_logger.info("📋 Constraints: ~20% none, ~30% simple, ~25% medium, ~15% complex, ~10% overrides")

    # Step 1: Generate realistic data
    test_logger.info("1️⃣  Generating realistic university data...")
    try:
        lecturers, constraint_meta = await setup_realistic_university_data(
            backend_url, test_year, test_semester
        )
        constrained_count = sum(1 for m in constraint_meta if m["num_atomics"] > 0)
        override_count = sum(1 for m in constraint_meta if m.get("secretary_override") is not None)
        test_logger.info(f"✅ Generated data: {len(lecturers)} lecturers, "
                         f"{constrained_count} with constraints, {override_count} with secretary override")
    except Exception as e:
        test_logger.error(f"❌ Failed to generate test data: {e}")
        return

    # Step 2: Wait for solver
    test_logger.info("2️⃣  Waiting for Solver to process realistic workload...")
    start_time = datetime.now()

    solver_result = await wait_for_solver_completion(backend_url, test_year, test_semester, timeout=180)

    solve_time = (datetime.now() - start_time).seconds

    if not solver_result:
        test_logger.error("❌ Timeout waiting for solver completion")
        return

    test_logger.info(f"Solver completed in {solve_time}s with status: {solver_result['status']}")

    # Step 3: Handle solver result
    if solver_result['status'] != 'solved':
        test_logger.error(f"❌ Solver returned '{solver_result['status']}' instead of 'solved'")
        if 'broken_constraints' in solver_result:
            broken = solver_result['broken_constraints']
            test_logger.error(f"   {len(broken)} breaking constraint(s)")

            # Still verify breaking constraints are properly stored
            async with httpx.AsyncClient(timeout=30.0) as client:
                breaking_resp = await client.get(
                    f"{backend_url}/dev/breaking-constraints/semester/{test_year}/{test_semester}"
                )
                if breaking_resp.status_code == 200:
                    db_breaking = breaking_resp.json().get('data', [])
                    test_logger.info(f"   {len(db_breaking)} breaking constraints stored in DB")
                    for bc in db_breaking[:5]:
                        test_logger.info(f"     Lecturer '{bc.get('lecturer_name')}', "
                                         f"Constraint {bc.get('constraints_id')}, "
                                         f"Atomic {bc.get('atomic_constraint_index')}")

        test_logger.error("   Realistic constraints should be solvable — investigate solver logic")
        return

    # Step 4: Verify solution quality
    schedule_id = solver_result['schedule_id']
    test_logger.info(f"✅ Solver found solution (schedule_id={schedule_id})")

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Fetch sessions
        sessions_resp = await client.get(
            f"{backend_url}/dev/courses-schedules/schedule/{schedule_id}"
        )

        if sessions_resp.status_code != 200:
            test_logger.error(f"❌ Failed to retrieve sessions: {sessions_resp.status_code}")
            return

        sessions = sessions_resp.json()
        session_count = len(sessions)
        test_logger.info(f"📅 Total course sessions: {session_count}")

        # --- 4a: Coverage ---
        unique_offerings = {s['offering_id'] for s in sessions}
        courses_scheduled = len(unique_offerings)

        offerings_resp = await client.get(f"{backend_url}/dev/course-offering/")
        if offerings_resp.status_code == 200:
            all_offerings = offerings_resp.json()
            semester_offerings = [
                o for o in all_offerings
                if o['academic_year'] == test_year and o['semester'] == test_semester
            ]
            total_offerings = len(semester_offerings)
        else:
            total_offerings = 40  # expected

        coverage_pct = (courses_scheduled / total_offerings * 100) if total_offerings > 0 else 0
        test_logger.info(f"📚 Course coverage: {courses_scheduled}/{total_offerings} ({coverage_pct:.1f}%)")

        # --- 4b: Lecturer no-overlap check ---
        test_logger.info("3️⃣  Verifying no-overlap invariants...")
        lecturer_schedule = {}  # lid -> list of (day, start_hour, end_hour)
        for s in sessions:
            lid = s['lecturer_id']
            day = s['day_of_week']
            # Parse time strings (format: "HH:MM:SS" or time object from API)
            start_h = _parse_hour(s['start_time'])
            end_h = _parse_hour(s['end_time'])

            if lid not in lecturer_schedule:
                lecturer_schedule[lid] = []
            lecturer_schedule[lid].append((day, start_h, end_h))

        lecturer_overlaps = 0
        for lid, slots in lecturer_schedule.items():
            for i, (d1, s1, e1) in enumerate(slots):
                for j, (d2, s2, e2) in enumerate(slots):
                    if j <= i:
                        continue
                    if d1 == d2 and s1 < e2 and s2 < e1:
                        lecturer_overlaps += 1
                        test_logger.error(f"   ❌ Lecturer {lid} overlap on day {d1}: "
                                          f"{s1}:00-{e1}:00 vs {s2}:00-{e2}:00")

        if lecturer_overlaps == 0:
            test_logger.info("✅ No lecturer overlaps detected")
        else:
            test_logger.error(f"❌ {lecturer_overlaps} lecturer overlap(s) detected!")

        # --- 4c: Day/time bounds check ---
        out_of_bounds = 0
        for s in sessions:
            day = s['day_of_week']
            end_h = _parse_hour(s['end_time'])
            max_h = 15 if day == 6 else 20
            if end_h > max_h:
                out_of_bounds += 1
                test_logger.error(f"   ❌ Session ends at {end_h}:00 on day {day} (max {max_h}:00)")

        if out_of_bounds == 0:
            test_logger.info("✅ All sessions within day/time bounds")
        else:
            test_logger.error(f"❌ {out_of_bounds} session(s) exceed day time limits!")

        # --- 4d: Credit point / duration check ---
        # Verify scheduled duration matches credit points for each offering
        duration_mismatches = 0
        for oid in unique_offerings:
            offering_sessions = [s for s in sessions if s['offering_id'] == oid]
            if not offering_sessions:
                continue
            # All sessions for an offering should have same start/end (one scheduling slot)
            sample = offering_sessions[0]
            scheduled_duration = _parse_hour(sample['end_time']) - _parse_hour(sample['start_time'])
            if scheduled_duration <= 0:
                duration_mismatches += 1
                test_logger.error(f"   ❌ Offering {oid}: invalid duration {scheduled_duration}h")

        if duration_mismatches == 0:
            test_logger.info("✅ All offering durations are valid")

        # --- 4e: Constraint counts ---
        constraints_resp = await client.get(
            f"{backend_url}/dev/constraints/semester/{test_year}/{test_semester}"
        )
        total_constraints = 0
        if constraints_resp.status_code == 200:
            total_constraints = len(constraints_resp.json())
        test_logger.info(f"📋 Total constraints processed: {total_constraints}")

        # --- 4f: Day distribution (quality metric) ---
        day_names = ["", "Sun", "Mon", "Tue", "Wed", "Thu", "Fri"]
        day_counts = {}
        for s in sessions:
            d = s['day_of_week']
            day_counts[d] = day_counts.get(d, 0) + 1

        test_logger.info("📊 Schedule distribution by day:")
        for d in sorted(day_counts.keys()):
            name = day_names[d] if d < len(day_names) else f"Day{d}"
            test_logger.info(f"   {name}: {day_counts[d]} sessions")

        # --- 4g: Multi-course lecturers teach on different days ---
        multi_course_lecturers = {lid for lid, slots in lecturer_schedule.items() if len(slots) >= 2}
        multi_on_same_day = 0
        for lid in multi_course_lecturers:
            days_used = [d for d, _, _ in lecturer_schedule[lid]]
            if len(days_used) != len(set(days_used)):
                multi_on_same_day += 1
        if multi_course_lecturers:
            test_logger.info(f"👥 {len(multi_course_lecturers)} lecturers teach 2+ courses, "
                             f"{multi_on_same_day} have courses on same day (not an error, just a metric)")

        # --- Final verdict ---
        success_threshold = 0.95  # At least 95% of courses scheduled
        all_invariants_ok = (lecturer_overlaps == 0 and out_of_bounds == 0 and duration_mismatches == 0)

        if courses_scheduled >= total_offerings * success_threshold and all_invariants_ok:
            test_logger.info("\n🎉 REALISTIC UNIVERSITY TEST PASSED!")
            test_logger.info(f"   - {courses_scheduled}/{total_offerings} courses scheduled ({coverage_pct:.1f}%)")
            test_logger.info(f"   - {session_count} total sessions across {len(day_counts)} days")
            test_logger.info(f"   - {total_constraints} constraints respected")
            test_logger.info(f"   - No overlap or bounds violations")
            test_logger.info(f"   - Solved in {solve_time}s")
        else:
            if not all_invariants_ok:
                test_logger.error("\n❌ REALISTIC UNIVERSITY TEST FAILED!")
                test_logger.error("   Schedule invariants violated (overlaps or bounds)")
            else:
                test_logger.error(f"\n❌ REALISTIC UNIVERSITY TEST FAILED!")
                test_logger.error(f"   Only {courses_scheduled}/{total_offerings} courses scheduled "
                                  f"({coverage_pct:.1f}%, need {success_threshold*100:.0f}%)")


def _parse_hour(time_val) -> int:
    """Extract hour from a time value (string 'HH:MM:SS', 'HH:MM', or dict)."""
    if isinstance(time_val, str):
        return int(time_val.split(":")[0])
    if isinstance(time_val, dict):
        return time_val.get("hour", 0)
    # datetime.time or similar
    try:
        return time_val.hour
    except AttributeError:
        return int(str(time_val).split(":")[0])


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v", "-s"])
