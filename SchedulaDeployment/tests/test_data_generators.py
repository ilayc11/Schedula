"""
Shared data generation functions for testing different CSP solver scenarios.

This module provides functions to populate the database with test data for:
- Happy path: Simple constraints that are easy to satisfy
- Over-constrained: Multiple overlapping constraints that are challenging but solvable
- Failure path: Impossible-to-satisfy constraints that should cause solver failure
"""

import asyncio
import httpx
import random
import uuid
import json
from datetime import datetime


# Helper Functions

async def wait_for_solver_completion(base_url, year, semester_num, timeout=120):
    """
    Wait for solver to complete by polling the backend API.
    
    This function waits for the solver to finish processing all pending constraint
    updates. Since the solver uses batching with a timeout delay, we need to:
    1. Account for the batch timeout (solver waits BATCH_TIMEOUT_SECONDS after last message)
    2. Wait for a solver_run record to exist
    3. Wait for the status to be 'solved' or 'failed'
    4. Ensure the result is stable (hasn't changed for multiple checks)
    
    Args:
        base_url: Backend API base URL
        year: Semester year
        semester_num: Semester number
        timeout: Maximum seconds to wait
    
    Returns:
        Dict with solver response containing:
            - schedule_id: int (or None)
            - semester_year: int
            - semester_number: int
            - status: "pending", "solved", or "failed"
            - broken_constraints: list (if failed)
        
        Returns None if timeout or error
    """
    start_time = asyncio.get_event_loop().time()
    last_update_time = None
    stable_result = None
    stability_counter = 0
    # Solver batching config (must match solver/src/main.py)
    SOLVER_BATCH_TIMEOUT = 1.5  # BATCH_TIMEOUT_SECONDS in solver
    SOLVER_MAX_BATCH_WAIT = 3.0  # MAX_BATCH_WAIT_SECONDS in solver
    # Test polling config
    STABILITY_CHECKS = 3  # Number of consecutive identical results needed
    CHECK_INTERVAL = 0.5  # Poll every 0.5 seconds for faster response
    
    print(f"Polling backend API for solver completion (timeout: {timeout}s)...")
    
    # Track initial wait to allow solver batch timer to trigger
    initial_wait_done = False
    last_status_msg = ""
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        while True:
            try:
                # Poll the solver_runs endpoint
                resp = await client.get(
                    f"{base_url}/dev/solver-runs/semester/{year}/{semester_num}"
                )
                
                if resp.status_code == 200:
                    solver_run = resp.json()
                    status = solver_run.get('status')
                    completed_at = solver_run.get('completed_at')
                    
                    if status in ['solved', 'failed']:
                        # Check if this result is stable (hasn't changed for multiple checks)
                        current_result = {
                            'schedule_id': solver_run.get('schedule_id'),
                            'semester_year': solver_run['semester_year'],
                            'semester_number': solver_run['semester_number'],
                            'status': status,
                            'completed_at': completed_at
                        }
                        
                        if status == 'failed':
                            broken = solver_run.get('broken_constraints', [])
                            if isinstance(broken, str):
                                broken = json.loads(broken)
                            current_result['broken_constraints'] = broken
                        
                        # Check if result is stable
                        if stable_result == current_result:
                            stability_counter += 1
                            # Only print first and last stability check
                            if stability_counter == 1 or stability_counter == STABILITY_CHECKS:
                                print(f"  Verifying stability... ({stability_counter}/{STABILITY_CHECKS})")
                        else:
                            stable_result = current_result
                            stability_counter = 1
                            print(f"  Solver status: {status}, verifying...")
                        
                        # If stable for required checks, return
                        if stability_counter >= STABILITY_CHECKS:
                            print(f"\u2713 Solver completed with status: {status}")
                            return stable_result
                    
                    elif status == 'pending':
                        # Only print if status changed
                        status_msg = "pending"
                        if status_msg != last_status_msg:
                            print(f"  Solver status: pending...")
                            last_status_msg = status_msg
                        stability_counter = 0
                        stable_result = None
                    else:
                        print(f"  Unknown solver status: {status}")
                
                elif resp.status_code == 404:
                    # No solver run yet - this is expected initially
                    # The solver may still be waiting for its batch timeout to expire
                    if not initial_wait_done:
                        elapsed = asyncio.get_event_loop().time() - start_time
                        if elapsed < SOLVER_MAX_BATCH_WAIT + 1:  # Add 1s buffer
                            # Don't spam - only print once
                            if elapsed < 1.0:
                                print(f"  Waiting for solver to start (batching messages)...")
                        else:
                            initial_wait_done = True
                    
                    stability_counter = 0
                    stable_result = None
                else:
                    print(f"  Unexpected API response: {resp.status_code}")
                
            except httpx.HTTPError as e:
                # Don't spam errors on every poll
                pass
            except Exception as e:
                print(f"  Error polling solver: {e}")
            
            # Check timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout:
                print(f"\u2a2f Timeout waiting for solver ({timeout}s)")
                return None
            
            # Wait before next poll
            await asyncio.sleep(CHECK_INTERVAL)


# Core Infrastructure Functions

async def clear_database(client, base_url):
    """Clear all data from the database."""
    print("Clearing database...")
    try:
        resp = await client.delete(f"{base_url}/db/clear")
        resp.raise_for_status()
        print("Database cleared.")
        await asyncio.sleep(2)  # Wait for DB to settle
    except Exception as e:
        print(f"Failed to clear database: {e}")
        raise


async def create_semester(client, base_url, year, semester_num, status="SUB"):
    """Create a test semester."""
    print(f"Creating Semester {year}-{semester_num}...")
    semester_data = {
        "semester_year": year,
        "semester_number": semester_num,
        "semester_start_date": f"{year}-03-01",
        "semester_end_date": f"{year}-07-01",
        "constraint_start_date": f"{year}-03-01",
        "constraint_end_date": f"{year}-06-15",
        "change_period_start": f"{year}-06-16",
        "change_period_end": f"{year}-06-30",
        "status": status
    }
    try:
        resp = await client.post(f"{base_url}/dev/semesters/", json=semester_data)
        resp.raise_for_status()
        print("Semester created.")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            print("Semester might already exist, continuing...")
        else:
            print(f"Error creating semester: {e}")
            raise


async def create_lecturers(client, base_url, num_lecturers):
    """Create lecturer users and return their details."""
    print(f"Creating {num_lecturers} lecturers...")
    lecturers = []
    for i in range(1, num_lecturers + 1):
        user_id = f"999{i:06d}"  # 9 digit ID
        user_name = f"lecturer{i}"
        email = f"lecturer{i}@example.com"
        
        user_data = {
            "user_id": user_id,
            "user_name": user_name,
            "first_name": "Lecturer",
            "last_name": f"{i}",
            "email": email,
            "role": "L",
            "department_id": 1
        }
        
        try:
            # Create
            resp = await client.post(f"{base_url}/dev/users/", json=user_data)
            if resp.status_code != 201 and resp.status_code != 400:
                resp.raise_for_status()
            
            # Fetch to get internal ID
            resp = await client.get(f"{base_url}/dev/users/{user_name}")
            resp.raise_for_status()
            user = resp.json()
            lecturers.append(user)
            
        except Exception as e:
            print(f"Failed to create/fetch user {user_name}: {e}")

    print(f"Successfully processed {len(lecturers)} lecturers.")
    return lecturers


async def create_courses_and_offerings(client, base_url, num_courses, year, semester_num):
    """Create courses and offerings for a semester."""
    print(f"Creating {num_courses} courses and offerings...")
    
    # Distribute courses across departments 100-500
    departments = [100, 200, 300, 400, 500]
    
    for i in range(1, num_courses + 1):
        dept_id = departments[(i - 1) % len(departments)]
        course_number = dept_id * 10000 + i  # e.g., 1000001, 2000002, etc.
        course_data = {
            "department_id": dept_id,
            "degree_level": 1,
            "course_number": course_number,
            "course_name": f"Test Course {i}",
            "credit_points": 3.0
        }
        
        try:
            # Create Course
            resp = await client.post(f"{base_url}/dev/courses/", json=course_data)
            if resp.status_code != 201 and resp.status_code != 400:
                resp.raise_for_status()

            # Create Offering with cohorts
            offering_data = {
                "course_number": course_number,
                "academic_year": year,
                "semester": semester_num,
                "group_number": 1,
                "cohorts": [
                    {
                        "target_department_id": dept_id,
                        "target_year_level": ((i - 1) % 4) + 1  # Distribute across years 1-4
                    }
                ]
            }
            
            resp = await client.post(f"{base_url}/dev/course-offering/", json=offering_data)
            if resp.status_code != 201 and resp.status_code != 400:
                resp.raise_for_status()
                
        except Exception as e:
            print(f"Failed to create course/offering {course_number}: {e}")

    # Fetch all offerings to get IDs
    print("Fetching created offerings...")
    resp = await client.get(f"{base_url}/dev/course-offering/")
    resp.raise_for_status()
    all_offerings = resp.json()
    
    # Filter for our semester
    my_offerings = [
        o for o in all_offerings 
        if o['academic_year'] == year and o['semester'] == semester_num
    ]
    
    print(f"Found {len(my_offerings)} offerings for this semester.")
    return my_offerings


async def assign_lecturers(client, base_url, lecturers, offerings):
    """Assign lecturers to course offerings using round-robin."""
    print("Assigning lecturers to offerings...")
    assignments = 0
    
    # Round robin assignment
    for idx, offering in enumerate(offerings):
        lecturer = lecturers[idx % len(lecturers)]
        
        assignment_data = {
            "lecturer_internal_id": lecturer['user_internal_id'],
            "offering_id": offering['offering_id'],
            "role": "instructor"
        }
        
        try:
            resp = await client.post(f"{base_url}/dev/lecturer-courses/", json=assignment_data)
            if resp.status_code == 201:
                assignments += 1
        except Exception as e:
            print(f"Failed assignment: {e}")
            
    print(f"Created {assignments} lecturer assignments.")


# Scenario-Specific Constraint Generators

async def create_happy_path_constraints(client, base_url, lecturers, year, semester_num):
    """
    Create simple constraints - one block per lecturer (easy to solve).
    Each lecturer blocks ONE morning or afternoon on a random day.
    """
    print("Creating happy path constraints for lecturers...")
    count = 0
    total = len(lecturers)
    
    for i, lecturer in enumerate(lecturers):
        # Show progress every 10 lecturers
        if (i + 1) % 10 == 0 or (i + 1) == total:
            print(f"  Progress: {i + 1}/{total} constraints...", flush=True)
        
        day = random.randint(1, 5)  # Sun-Thu
        is_morning = random.choice([True, False])
        
        if is_morning:
            start_h, end_h = 8, 12
            text = "mornings"
        else:
            start_h, end_h = 14, 18
            text = "afternoons"
            
        day_name = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"][day-1]
        
        constraint_data = {
            "lecturer_internal_id": lecturer['user_internal_id'],
            "schedule_id": None,
            "semester_year": year,
            "semester_number": semester_num,
            "raw_text": f"I cannot teach on {day_name} {text}.",
            "structured_rules": {
                "atomic_constraints": [
                    {
                        "type": "block",
                        "days": [day],
                        "time_slot": {
                            "start_hour": start_h,
                            "end_hour": end_h
                        }
                    }
                ]
            },
            "secretary_override_as_hard": None
        }
        
        try:
            resp = await client.post(f"{base_url}/dev/constraints/", json=constraint_data)
            if resp.status_code == 201:
                count += 1
        except Exception:
            pass  # Errors will be reflected in final count
            
    print(f"✓ Created {count}/{total} happy path constraints.")


async def create_over_constrained_constraints(client, base_url, lecturers, year, semester_num):
    """
    Create multiple overlapping constraints per lecturer (challenging but solvable).
    - 30% of lecturers: 1-2 blocks
    - 50% of lecturers: 3-4 blocks
    - 20% of lecturers: 5-6 blocks
    """
    print("Creating over-constrained constraints for lecturers...")
    count = 0
    total = len(lecturers)
    day_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    
    for i, lecturer in enumerate(lecturers):
        # Show progress every 10 lecturers
        if (i + 1) % 10 == 0 or (i + 1) == total:
            print(f"  Progress: {i + 1}/{total} constraints...", flush=True)
        
        # Categorize lecturers by constraint intensity
        lecturer_pct = (i % 10) / 10.0
        
        if lecturer_pct < 0.3:
            num_blocks = random.randint(1, 2)
        elif lecturer_pct < 0.8:
            num_blocks = random.randint(3, 4)
        else:
            num_blocks = random.randint(5, 6)
        
        # Generate multiple atomic constraints
        atomic_constraints = []
        blocked_times = []  # Track blocked times
        
        for block_idx in range(num_blocks):
            day = random.randint(1, 5)
            
            # Define time blocks with variety
            time_blocks = [
                (8, 10, "early morning"),
                (9, 12, "mornings"),
                (10, 13, "late morning"),
                (12, 14, "midday"),
                (14, 16, "early afternoon"),
                (14, 18, "afternoons"),
                (16, 18, "late afternoon"),
                (17, 20, "evening")
            ]
            
            # For heavy constraints, prefer broader blocks
            if num_blocks >= 5:
                time_blocks = [tb for tb in time_blocks if tb[1] - tb[0] >= 3]
            
            start_h, end_h, time_desc = random.choice(time_blocks)
            
            # Avoid duplicates
            time_key = f"{day}_{start_h}_{end_h}"
            if time_key not in blocked_times:
                blocked_times.append(time_key)
                day_name = day_names[day - 1]
                
                atomic_constraints.append({
                    "type": "block",
                    "days": [day],
                    "time_slot": {
                        "start_hour": start_h,
                        "end_hour": end_h
                    },
                    "original_text": f"{day_name} {time_desc}"  # Keep for text generation
                })
        
        # Create descriptive constraint text
        if len(atomic_constraints) == 1:
            day_name = day_names[atomic_constraints[0]['days'][0] - 1]
            raw_text = f"I cannot teach on {day_name} {atomic_constraints[0]['original_text']}."
        elif len(atomic_constraints) == 2:
            desc1 = f"{day_names[atomic_constraints[0]['days'][0] - 1]} {atomic_constraints[0]['original_text']}"
            desc2 = f"{day_names[atomic_constraints[1]['days'][0] - 1]} {atomic_constraints[1]['original_text']}"
            raw_text = f"I cannot teach on {desc1} or {desc2}."
        else:
            parts = [f"{day_names[ac['days'][0] - 1]} {ac['original_text']}" 
                     for ac in atomic_constraints[:3]]
            raw_text = f"I cannot teach on {', '.join(parts[:-1])}, or {parts[-1]}."
            if len(atomic_constraints) > 3:
                raw_text += f" Plus {len(atomic_constraints) - 3} more restrictions."
        
        # Remove original_text before saving (only used for text generation)
        saved_atomics = [
            {
                "type": ac["type"],
                "days": ac["days"],
                "time_slot": ac["time_slot"]
            }
            for ac in atomic_constraints
        ]
        
        constraint_data = {
            "lecturer_internal_id": lecturer['user_internal_id'],
            "schedule_id": None,
            "semester_year": year,
            "semester_number": semester_num,
            "raw_text": raw_text,
            "structured_rules": {
                "atomic_constraints": saved_atomics
            },
            "secretary_override_as_hard": None
        }
        
        try:
            resp = await client.post(f"{base_url}/dev/constraints/", json=constraint_data)
            if resp.status_code == 201:
                count += 1
        except Exception:
            pass  # Errors will be reflected in final count
    
    print(f"✓ Created {count}/{total} over-constrained constraints.")


async def create_failure_path_constraints(client, base_url, lecturers, year, semester_num):
    """
    Create impossible-to-satisfy constraints.
    Each lecturer blocks ALL days from 8am to 8pm, making scheduling impossible.
    """
    print("Creating failure path constraints (impossible to satisfy)...")
    count = 0
    total = len(lecturers)
    day_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    
    for i, lecturer in enumerate(lecturers):
        # Show progress every 10 lecturers
        if (i + 1) % 10 == 0 or (i + 1) == total:
            print(f"  Progress: {i + 1}/{total} constraints...", flush=True)
        
        # Block all weekdays, all day long
        atomic_constraints = []
        
        for day in range(1, 7):  # Sun-Fri (all 6 days)
            # Friday (day 6) has different hours: 8-15 instead of 8-20
            end_hour = 15 if day == 6 else 20
            
            atomic_constraints.append({
                "type": "block",
                "days": [day],
                "time_slot": {
                    "start_hour": 8,
                    "end_hour": end_hour
                }
            })
        
        raw_text = "I cannot teach on Sunday, Monday, Tuesday, Wednesday, Thursday, or Friday."
        
        constraint_data = {
            "lecturer_internal_id": lecturer['user_internal_id'],
            "schedule_id": None,
            "semester_year": year,
            "semester_number": semester_num,
            "raw_text": raw_text,
            "structured_rules": {
                "atomic_constraints": atomic_constraints
            },
            "secretary_override_as_hard": None
        }
        
        try:
            resp = await client.post(f"{base_url}/dev/constraints/", json=constraint_data)
            if resp.status_code == 201:
                count += 1
        except Exception:
            pass  # Errors will be reflected in final count
    
    print(f"✓ Created {count}/{total} failure path constraints (all days blocked).")


# High-Level Setup Functions

async def setup_happy_path_data(base_url, year, semester_num, num_lecturers=50, num_courses=50):
    """
    Complete setup for happy path testing.
    Returns lecturers list for further testing.
    """
    print("\n" + "="*60)
    print(f"SETTING UP HAPPY PATH DATA")
    print(f"Lecturers: {num_lecturers}, Courses: {num_courses}")
    print("="*60 + "\n")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        await clear_database(client, base_url)
        await create_semester(client, base_url, year, semester_num)
        lecturers = await create_lecturers(client, base_url, num_lecturers)
        
        if not lecturers:
            raise Exception("No lecturers created")
        
        offerings = await create_courses_and_offerings(client, base_url, num_courses, year, semester_num)
        
        if not offerings:
            raise Exception("No offerings created")
        
        await assign_lecturers(client, base_url, lecturers, offerings)
        await create_happy_path_constraints(client, base_url, lecturers, year, semester_num)
        
        # Wait for RabbitMQ messages to be sent and solver to receive them
        # This ensures the solver's batch timer has started before we start polling
        print("\nWaiting for constraint messages to reach solver...")
        await asyncio.sleep(2.0)  # Allow time for all messages to be sent and received
    
    print("\n✅ Happy path data generation complete!\n")
    return lecturers


async def setup_over_constrained_data(base_url, year, semester_num, num_lecturers=50, num_courses=50):
    """
    Complete setup for over-constrained testing.
    Returns lecturers list for further testing.
    """
    print("\n" + "="*60)
    print(f"SETTING UP OVER-CONSTRAINED DATA")
    print(f"Lecturers: {num_lecturers}, Courses: {num_courses}")
    print("="*60 + "\n")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        await clear_database(client, base_url)
        await create_semester(client, base_url, year, semester_num)
        lecturers = await create_lecturers(client, base_url, num_lecturers)
        
        if not lecturers:
            raise Exception("No lecturers created")
        
        offerings = await create_courses_and_offerings(client, base_url, num_courses, year, semester_num)
        
        if not offerings:
            raise Exception("No offerings created")
        
        await assign_lecturers(client, base_url, lecturers, offerings)
        await create_over_constrained_constraints(client, base_url, lecturers, year, semester_num)
        
        # Wait for RabbitMQ messages to be sent and solver to receive them
        # This ensures the solver's batch timer has started before we start polling
        print("\nWaiting for constraint messages to reach solver...")
        await asyncio.sleep(2.0)  # Allow time for all messages to be sent and received
    
    print("\n✅ Over-constrained data generation complete!\n")
    return lecturers


async def setup_failure_path_data(base_url, year, semester_num, num_lecturers=50, num_courses=50):
    """
    Complete setup for failure path testing.
    Returns lecturers list for further testing.
    """
    print("\n" + "="*60)
    print(f"SETTING UP FAILURE PATH DATA")
    print(f"Lecturers: {num_lecturers}, Courses: {num_courses}")
    print("="*60 + "\n")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        await clear_database(client, base_url)
        await create_semester(client, base_url, year, semester_num)
        lecturers = await create_lecturers(client, base_url, num_lecturers)
        
        if not lecturers:
            raise Exception("No lecturers created")
        
        offerings = await create_courses_and_offerings(client, base_url, num_courses, year, semester_num)
        
        if not offerings:
            raise Exception("No offerings created")
        
        await assign_lecturers(client, base_url, lecturers, offerings)
        await create_failure_path_constraints(client, base_url, lecturers, year, semester_num)
        
        # Wait for RabbitMQ messages to be sent and solver to receive them
        # This ensures the solver's batch timer has started before we start polling
        print("\nWaiting for constraint messages to reach solver...")
        await asyncio.sleep(2.0)  # Allow time for all messages to be sent and received
    
    print("\n✅ Failure path data generation complete!\n")
    return lecturers


# --- Realistic University Scenario ---

async def create_realistic_courses_and_offerings(client, base_url, year, semester_num):
    """
    Create courses with varied credit points and cross-department cohorts.
    
    Returns list of offering dicts with metadata about cohorts and department.
    
    Departments:
        100 = Computer Science
        200 = Mathematics
        300 = Electrical Engineering
    
    Creates 40 courses:
        - 15 CS, 13 Math, 12 EE (owning department)
        - Credit points vary: 2, 3, 4, or 5
        - ~6 courses are cross-listed (multi-cohort)
    """
    departments = [100, 200, 300]
    dept_names = {100: "CS", 200: "Math", 300: "EE"}
    
    # Course definitions: (owning_dept, credit_points, cohorts)
    # cohorts is a list of (target_dept, target_year) tuples
    course_defs = [
        # --- CS courses (15) ---
        (100, 4, [(100, 1)]),                       # Intro to CS – CS year 1
        (100, 4, [(100, 1)]),                       # Discrete Math – CS year 1
        (100, 3, [(100, 2)]),                       # Data Structures – CS year 2
        (100, 3, [(100, 2)]),                       # Algorithms – CS year 2
        (100, 3, [(100, 2), (200, 2)]),             # Linear Algebra (cross-listed CS+Math year 2)
        (100, 2, [(100, 3)]),                       # Operating Systems – CS year 3
        (100, 3, [(100, 3)]),                       # Databases – CS year 3
        (100, 2, [(100, 3)]),                       # Computer Networks – CS year 3
        (100, 3, [(100, 3), (300, 3)]),             # Signals & Systems (cross-listed CS+EE year 3)
        (100, 2, [(100, 4)]),                       # Machine Learning – CS year 4
        (100, 2, [(100, 4)]),                       # Seminar in CS – CS year 4
        (100, 5, [(100, 4)]),                       # Final Project – CS year 4
        (100, 3, [(100, 2)]),                       # Probability – CS year 2
        (100, 4, [(100, 1), (200, 1)]),             # Calculus I (cross-listed CS+Math year 1)
        (100, 2, [(100, 3)]),                       # Software Engineering – CS year 3
        # --- Math courses (13) ---
        (200, 4, [(200, 1)]),                       # Calculus II – Math year 1
        (200, 3, [(200, 1)]),                       # Set Theory – Math year 1
        (200, 3, [(200, 2)]),                       # Abstract Algebra – Math year 2
        (200, 4, [(200, 2)]),                       # Real Analysis – Math year 2
        (200, 3, [(200, 2), (100, 3)]),             # Numerical Methods (cross-listed Math+CS)
        (200, 2, [(200, 3)]),                       # Complex Analysis – Math year 3
        (200, 2, [(200, 3)]),                       # Topology – Math year 3
        (200, 3, [(200, 3)]),                       # Differential Equations – Math year 3
        (200, 2, [(200, 4)]),                       # Seminar in Math – Math year 4
        (200, 5, [(200, 4)]),                       # Thesis – Math year 4
        (200, 3, [(200, 1)]),                       # Logic – Math year 1
        (200, 4, [(200, 2)]),                       # Measure Theory – Math year 2
        (200, 2, [(200, 3)]),                       # Number Theory – Math year 3
        # --- EE courses (12) ---
        (300, 4, [(300, 1)]),                       # Circuits I – EE year 1
        (300, 3, [(300, 1)]),                       # Physics for Engineers – EE year 1
        (300, 4, [(300, 1), (100, 1)]),             # Intro to Programming (cross-listed EE+CS year 1)
        (300, 3, [(300, 2)]),                       # Electromagnetics – EE year 2
        (300, 3, [(300, 2)]),                       # Digital Logic – EE year 2
        (300, 2, [(300, 2)]),                       # Electronics I – EE year 2
        (300, 3, [(300, 3)]),                       # Control Systems – EE year 3
        (300, 2, [(300, 3)]),                       # Communication Systems – EE year 3
        (300, 3, [(300, 3), (200, 3)]),             # Applied Math for Engineers (cross-listed EE+Math)
        (300, 2, [(300, 4)]),                       # VLSI Design – EE year 4
        (300, 5, [(300, 4)]),                       # Final Project – EE year 4
        (300, 2, [(300, 4)]),                       # Seminar in EE – EE year 4
    ]
    
    print(f"Creating {len(course_defs)} realistic courses and offerings...")
    
    cross_listed_count = sum(1 for _, _, cohorts in course_defs if len(cohorts) > 1)
    print(f"  {cross_listed_count} cross-listed courses (multi-cohort)")
    
    for i, (dept_id, credit_points, cohorts) in enumerate(course_defs):
        course_number = dept_id * 10000 + (i + 1)
        course_data = {
            "department_id": dept_id,
            "degree_level": 1,
            "course_number": course_number,
            "course_name": f"{dept_names[dept_id]} Course {i + 1}",
            "credit_points": float(credit_points)
        }
        
        try:
            resp = await client.post(f"{base_url}/dev/courses/", json=course_data)
            if resp.status_code not in (201, 400):
                resp.raise_for_status()
            
            offering_data = {
                "course_number": course_number,
                "academic_year": year,
                "semester": semester_num,
                "group_number": 1,
                "cohorts": [
                    {"target_department_id": td, "target_year_level": ty}
                    for td, ty in cohorts
                ]
            }
            
            resp = await client.post(f"{base_url}/dev/course-offering/", json=offering_data)
            if resp.status_code not in (201, 400):
                resp.raise_for_status()
        except Exception as e:
            print(f"  Failed to create course {course_number}: {e}")
    
    # Fetch created offerings
    resp = await client.get(f"{base_url}/dev/course-offering/")
    resp.raise_for_status()
    all_offerings = resp.json()
    my_offerings = [
        o for o in all_offerings
        if o['academic_year'] == year and o['semester'] == semester_num
    ]
    
    print(f"  Created {len(my_offerings)} offerings for semester {year}-{semester_num}")
    return my_offerings, course_defs


async def assign_lecturers_realistic(client, base_url, lecturers, offerings, course_defs):
    """
    Assign lecturers realistically:
    - Each lecturer teaches 1-3 courses depending on seniority
    - Some courses are team-taught (2 lecturers)
    - Lecturers are assigned within their department where possible
    
    Returns a mapping: lecturer_internal_id -> list of offering_ids
    """
    departments = [100, 200, 300]
    dept_sizes = {100: 12, 200: 10, 300: 8}  # Matches create order
    
    # Group lecturers by department
    dept_lecturers = {}
    idx = 0
    for dept_id in departments:
        count = dept_sizes[dept_id]
        dept_lecturers[dept_id] = lecturers[idx:idx + count]
        idx += count
    
    # Group offerings by owning department  
    dept_offerings = {d: [] for d in departments}
    for offering, (dept_id, credit_points, cohorts) in zip(offerings, course_defs):
        dept_offerings[dept_id].append(offering)
    
    assignments = 0
    team_taught = 0
    lecturer_load = {}  # lecturer_id -> num courses
    
    print("Assigning lecturers to offerings (realistic distribution)...")
    
    for dept_id in departments:
        d_lecturers = dept_lecturers[dept_id]
        d_offerings = dept_offerings[dept_id]
        
        if not d_lecturers or not d_offerings:
            continue
        
        # Round-robin within department, but allow multiple courses per lecturer
        for i, offering in enumerate(d_offerings):
            lecturer = d_lecturers[i % len(d_lecturers)]
            lid = lecturer['user_internal_id']
            
            assignment_data = {
                "lecturer_internal_id": lid,
                "offering_id": offering['offering_id'],
                "role": "instructor"
            }
            
            try:
                resp = await client.post(f"{base_url}/dev/lecturer-courses/", json=assignment_data)
                if resp.status_code == 201:
                    assignments += 1
                    lecturer_load[lid] = lecturer_load.get(lid, 0) + 1
            except Exception as e:
                print(f"  Failed assignment: {e}")
            
            # Team-teach: add a second lecturer for ~15% of courses
            if i % 7 == 0 and len(d_lecturers) > 1:
                second_lecturer = d_lecturers[(i + 1) % len(d_lecturers)]
                second_lid = second_lecturer['user_internal_id']
                
                if second_lid != lid:
                    assignment_data2 = {
                        "lecturer_internal_id": second_lid,
                        "offering_id": offering['offering_id'],
                        "role": "instructor"
                    }
                    try:
                        resp = await client.post(f"{base_url}/dev/lecturer-courses/", json=assignment_data2)
                        if resp.status_code == 201:
                            assignments += 1
                            team_taught += 1
                            lecturer_load[second_lid] = lecturer_load.get(second_lid, 0) + 1
                    except Exception:
                        pass
    
    # Report load distribution
    loads = list(lecturer_load.values())
    multi_course = sum(1 for v in loads if v >= 2)
    print(f"  Created {assignments} lecturer-offering assignments ({team_taught} team-taught)")
    print(f"  {multi_course}/{len(loads)} lecturers teach 2+ courses")
    if loads:
        print(f"  Course load: min={min(loads)}, max={max(loads)}, avg={sum(loads)/len(loads):.1f}")


async def create_realistic_constraints(client, base_url, lecturers, year, semester_num):
    """
    Create varied, realistic constraints:
    
    - ~20% (6 lecturers): No constraints at all
    - ~30% (9 lecturers): 1 simple constraint (half-day block)
    - ~25% (8 lecturers): 2-3 constraints (e.g., full day + time slot)
    - ~15% (4 lecturers): Complex (3-4 blocks, some hard-priority)
    - ~10% (3 lecturers): Has secretary override
    
    Constraint types mirror real requests:
    - "I don't teach on Sundays" (religious/personal)
    - "Not before 10am" (mornings blocked)
    - "Wednesday is my research day" (full day blocked)
    - "Committee meeting Tuesday 14-16" (specific slot)
    - "No evenings – childcare" (late afternoon blocked on multiple days)
    
    Returns metadata about what constraints were created.
    """
    day_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    total = len(lecturers)
    count = 0
    constraint_meta = []  # Track what we created for verification
    
    # Shuffle lecturers for random distribution
    shuffled_indices = list(range(total))
    random.shuffle(shuffled_indices)
    
    # Define tier boundaries
    no_constraint_end = int(total * 0.20)        # 6
    simple_end = no_constraint_end + int(total * 0.30)  # 15
    medium_end = simple_end + int(total * 0.25)         # 22
    complex_end = medium_end + int(total * 0.15)        # 26
    # remaining: secretary override                     # 30
    
    print("Creating realistic constraints for lecturers...")
    print(f"  No constraints: {no_constraint_end}")
    print(f"  Simple (1 block): {simple_end - no_constraint_end}")
    print(f"  Medium (2-3 blocks): {medium_end - simple_end}")
    print(f"  Complex (3-4 blocks, some hard): {complex_end - medium_end}")
    print(f"  Secretary override: {total - complex_end}")
    
    for rank, idx in enumerate(shuffled_indices):
        lecturer = lecturers[idx]
        lid = lecturer['user_internal_id']
        
        # --- Tier 1: No constraints ---
        if rank < no_constraint_end:
            constraint_meta.append({
                "lecturer_internal_id": lid,
                "tier": "none",
                "num_atomics": 0
            })
            continue
        
        atomic_constraints = []
        raw_text_parts = []
        secretary_override = None
        
        # --- Tier 2: Simple (1 block) ---
        if rank < simple_end:
            variant = rank % 4
            if variant == 0:
                # "No Sundays"
                atomic_constraints.append({
                    "type": "block", "days": [1],
                    "time_slot": {"start_hour": 8, "end_hour": 20}
                })
                raw_text_parts.append("I cannot teach on Sundays.")
            elif variant == 1:
                # "No mornings on X"
                day = random.choice([2, 3, 4, 5])
                atomic_constraints.append({
                    "type": "block", "days": [day],
                    "time_slot": {"start_hour": 8, "end_hour": 12}
                })
                raw_text_parts.append(f"I cannot teach on {day_names[day-1]} mornings.")
            elif variant == 2:
                # "No afternoons on X"
                day = random.choice([2, 3, 4, 5])
                atomic_constraints.append({
                    "type": "block", "days": [day],
                    "time_slot": {"start_hour": 14, "end_hour": 18}
                })
                raw_text_parts.append(f"I cannot teach on {day_names[day-1]} afternoons.")
            else:
                # "Not on Friday"
                atomic_constraints.append({
                    "type": "block", "days": [6],
                    "time_slot": {"start_hour": 8, "end_hour": 15}
                })
                raw_text_parts.append("I cannot teach on Fridays.")
        
        # --- Tier 3: Medium (2-3 blocks) ---
        elif rank < medium_end:
            variant = rank % 3
            if variant == 0:
                # "Research day + specific meeting slot"
                research_day = random.choice([3, 4])  # Tue or Wed
                atomic_constraints.append({
                    "type": "block", "days": [research_day],
                    "time_slot": {"start_hour": 8, "end_hour": 20}
                })
                raw_text_parts.append(f"{day_names[research_day-1]} is my research day.")
                
                meeting_day = random.choice([d for d in [2, 3, 4, 5] if d != research_day])
                atomic_constraints.append({
                    "type": "block", "days": [meeting_day],
                    "time_slot": {"start_hour": 14, "end_hour": 16}
                })
                raw_text_parts.append(f"I have a committee meeting on {day_names[meeting_day-1]} 14:00-16:00.")
            elif variant == 1:
                # "No mornings on 2 different days"
                days = random.sample([2, 3, 4, 5], 2)
                for d in days:
                    atomic_constraints.append({
                        "type": "block", "days": [d],
                        "time_slot": {"start_hour": 8, "end_hour": 11}
                    })
                day_str = " or ".join(day_names[d-1] for d in days)
                raw_text_parts.append(f"I am not available before 11am on {day_str}.")
            else:
                # "No Sundays + no late afternoons Mon-Thu"
                atomic_constraints.append({
                    "type": "block", "days": [1],
                    "time_slot": {"start_hour": 8, "end_hour": 20}
                })
                raw_text_parts.append("I don't teach on Sundays.")
                
                for d in [2, 3]:
                    atomic_constraints.append({
                        "type": "block", "days": [d],
                        "time_slot": {"start_hour": 17, "end_hour": 20}
                    })
                raw_text_parts.append("I need to leave by 17:00 on Monday and Tuesday.")
        
        # --- Tier 4: Complex (3-4 blocks, some hard priority) ---
        elif rank < complex_end:
            # "Childcare constraints" – blocks late hours on most days + one full day
            childcare_day = random.choice([1, 6])  # Sunday or Friday fully blocked
            if childcare_day == 6:
                atomic_constraints.append({
                    "type": "block", "days": [6],
                    "time_slot": {"start_hour": 8, "end_hour": 15},
                    "priority": "hard"
                })
                raw_text_parts.append("I absolutely cannot teach on Fridays (childcare).")
            else:
                atomic_constraints.append({
                    "type": "block", "days": [1],
                    "time_slot": {"start_hour": 8, "end_hour": 20},
                    "priority": "hard"
                })
                raw_text_parts.append("I absolutely cannot teach on Sundays (childcare).")
            
            # Block late afternoon on 2-3 other days
            late_days = random.sample([2, 3, 4, 5], random.randint(2, 3))
            for d in late_days:
                atomic_constraints.append({
                    "type": "block", "days": [d],
                    "time_slot": {"start_hour": 16, "end_hour": 20},
                    "priority": "soft"
                })
            day_str = ", ".join(day_names[d-1] for d in late_days)
            raw_text_parts.append(f"I prefer not to teach after 16:00 on {day_str}.")
        
        # --- Tier 5: Secretary override ---
        else:
            # Reasonable constraints that the secretary has overridden
            override_as_hard = random.choice([True, False])
            secretary_override = override_as_hard
            
            day = random.choice([1, 2, 3])
            if day == 1:
                atomic_constraints.append({
                    "type": "block", "days": [1],
                    "time_slot": {"start_hour": 8, "end_hour": 20}
                })
                raw_text_parts.append("I cannot teach on Sundays.")
            else:
                atomic_constraints.append({
                    "type": "block", "days": [day],
                    "time_slot": {"start_hour": 8, "end_hour": 13}
                })
                raw_text_parts.append(f"I cannot teach on {day_names[day-1]} mornings.")
            
            # Second constraint
            other_day = random.choice([d for d in [3, 4, 5] if d != day])
            atomic_constraints.append({
                "type": "block", "days": [other_day],
                "time_slot": {"start_hour": 14, "end_hour": 18}
            })
            raw_text_parts.append(f"I cannot teach on {day_names[other_day-1]} afternoons.")
            
            override_label = f"override={'hard' if override_as_hard else 'soft'}"
            raw_text_parts.append(f"[Secretary {override_label}]")
        
        # Build and submit constraint
        constraint_data = {
            "lecturer_internal_id": lid,
            "schedule_id": None,
            "semester_year": year,
            "semester_number": semester_num,
            "raw_text": " ".join(raw_text_parts),
            "structured_rules": {"atomic_constraints": atomic_constraints},
            "secretary_override_as_hard": secretary_override
        }
        
        try:
            resp = await client.post(f"{base_url}/dev/constraints/", json=constraint_data)
            if resp.status_code == 201:
                count += 1
        except Exception:
            pass
        
        constraint_meta.append({
            "lecturer_internal_id": lid,
            "tier": (
                "simple" if rank < simple_end else
                "medium" if rank < medium_end else
                "complex" if rank < complex_end else
                "secretary_override"
            ),
            "num_atomics": len(atomic_constraints),
            "secretary_override": secretary_override
        })
    
    constrained = sum(1 for m in constraint_meta if m["num_atomics"] > 0)
    print(f"✓ Created {count}/{constrained} realistic constraints ({total - constrained} lecturers unconstrained).")
    return constraint_meta


async def setup_realistic_university_data(base_url, year, semester_num):
    """
    Complete setup for realistic university scenario.
    
    Creates a plausible small-university dataset:
    - 3 departments (CS=12, Math=10, EE=8 lecturers)
    - 40 courses with varied credits (2-5 hours)
    - Cross-listed courses, team-teaching, multi-course lecturers
    - Realistic constraint distribution
    
    Returns (lecturers, constraint_meta) for test verification.
    """
    num_lecturers = 30  # 12 CS + 10 Math + 8 EE
    
    print("\n" + "=" * 60)
    print("SETTING UP REALISTIC UNIVERSITY DATA")
    print(f"Lecturers: {num_lecturers} (3 departments), Courses: 40")
    print("=" * 60 + "\n")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        await clear_database(client, base_url)
        await create_semester(client, base_url, year, semester_num)
        lecturers = await create_lecturers(client, base_url, num_lecturers)
        
        if not lecturers:
            raise Exception("No lecturers created")
        
        offerings, course_defs = await create_realistic_courses_and_offerings(
            client, base_url, year, semester_num
        )
        
        if not offerings:
            raise Exception("No offerings created")
        
        await assign_lecturers_realistic(client, base_url, lecturers, offerings, course_defs)
        constraint_meta = await create_realistic_constraints(
            client, base_url, lecturers, year, semester_num
        )
        
        print("\nWaiting for constraint messages to reach solver...")
        await asyncio.sleep(2.0)
    
    print("\n✅ Realistic university data generation complete!\n")
    return lecturers, constraint_meta

