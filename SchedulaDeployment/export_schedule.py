import asyncio
import httpx
import csv
import os
from datetime import datetime

BASE_URL = "http://localhost:8000"
SEMESTER_YEAR = 2026
SEMESTER_NUMBER = 1
OUTPUT_FILE = "generated_schedule.csv"

async def fetch_schedule_id(client):
    """Fetch the latest schedule ID for the semester."""
    try:
        resp = await client.get(f"{BASE_URL}/dev/schedules/semester/{SEMESTER_YEAR}/{SEMESTER_NUMBER}")
        resp.raise_for_status()
        schedules = resp.json()
        
        if not schedules:
            print("No schedules found for this semester.")
            return None
            
        # Get the latest schedule (assuming higher ID is newer)
        latest_schedule = sorted(schedules, key=lambda x: x['schedule_id'], reverse=True)[0]
        return latest_schedule['schedule_id']
        
    except Exception as e:
        print(f"Error fetching schedule ID: {e}")
        return None

async def fetch_schedule_details(client, schedule_id):
    """Fetch detailed sessions for the schedule."""
    # We need a route that returns detailed sessions. 
    # Based on repositories/schedule_queries.py, get_detailed_schedule supports filtering by schedule_id.
    # However, looking at routes/dev_routes/schedules.py, there isn't a direct route exposing get_detailed_schedule by schedule_id only.
    # But /dev/schedules/my_schedule uses it.
    # Let's try to use the /dev/courses-schedules/ endpoint and filter manually or see if we can add a route.
    # Actually, let's check if there is a route that exposes the detailed view.
    # The repository function `get_detailed_schedule` is powerful.
    # Let's check if we can use `GET /dev/schedules/my_schedule` but that requires lecturer_id.
    
    # Alternative: Fetch all sessions from `/dev/courses-schedules/` and filter by schedule_id.
    # But that endpoint returns raw IDs, not names.
    
    # Best approach without modifying backend: 
    # 1. Fetch all sessions for the schedule from `/dev/courses-schedules/` (if it supports filtering by schedule, otherwise filter client side)
    # 2. Fetch courses and users to map IDs to names.
    
    print(f"Fetching sessions for Schedule ID: {schedule_id}...")
    
    try:
        # 1. Get all sessions
        resp = await client.get(f"{BASE_URL}/dev/courses-schedules/")
        resp.raise_for_status()
        all_sessions = resp.json()
        
        # Filter for our schedule
        schedule_sessions = [s for s in all_sessions if s['schedule_id'] == schedule_id]
        
        if not schedule_sessions:
            print("No sessions found in this schedule.")
            return []

        # 2. Get Metadata (Courses, Users, Offerings)
        # We need to map IDs to names for a readable CSV.
        
        # Fetch Users
        print("Fetching users metadata...")
        resp = await client.get(f"{BASE_URL}/dev/users/") # We assume this lists all users or we iterate.
        # Wait, /dev/users/ might not list all. Let's check the code.
        # src/repositories/users.py has list_users(). 
        # src/routes/dev_routes/users.py doesn't seem to have a list all route? 
        # Wait, I missed checking if there is a list all route in users.py.
        # Let's assume we can't easily get all users in one go if the route is missing.
        # But we generated them, so we know their IDs are sequential or we can fetch individually.
        
        # Actually, let's look at `generate_large_dataset.py`. We created users.
        # Let's try to fetch course offerings to get course numbers.
        
        print("Fetching course offerings...")
        resp = await client.get(f"{BASE_URL}/dev/course-offering/")
        resp.raise_for_status()
        offerings = {o['offering_id']: o for o in resp.json()}
        
        print("Fetching courses...")
        resp = await client.get(f"{BASE_URL}/dev/courses/")
        resp.raise_for_status()
        courses = {c['course_number']: c for c in resp.json()}
        
        # For lecturers, we might need to fetch them one by one if there's no list route.
        # Optimization: Collect unique lecturer IDs from sessions and fetch them.
        lecturer_ids = set(s['lecturer_internal_id'] for s in schedule_sessions)
        lecturers = {}
        
        print(f"Fetching details for {len(lecturer_ids)} lecturers...")
        for lid in lecturer_ids:
            # We need a route to get user by internal ID. 
            # /dev/users/{user_name} exists. 
            # /dev/users/email/{email} exists.
            # Is there get by ID? 
            # The code showed `get_user` by `user_name`.
            # We might be stuck without a direct ID lookup route in dev routes.
            # However, we can try to guess the username if we generated it (lecturer1, lecturer2...)
            # Or we can just show the ID in the CSV.
            pass

        # Let's try to construct the rows
        rows = []
        days = {1: "Sunday", 2: "Monday", 3: "Tuesday", 4: "Wednesday", 5: "Thursday", 6: "Friday", 7: "Saturday"}
        
        for session in schedule_sessions:
            offering = offerings.get(session['offering_id'])
            course = courses.get(offering['course_number']) if offering else None
            
            row = {
                "Session ID": session['session_id'],
                "Day": days.get(session['day_of_week'], "Unknown"),
                "Start Time": session['start_time'],
                "End Time": session['end_time'],
                "Course Name": course['course_name'] if course else "Unknown",
                "Course Number": course['course_number'] if course else "Unknown",
                "Group": offering['group_number'] if offering else "Unknown",
                "Lecturer ID": session['lecturer_internal_id']
            }
            rows.append(row)
            
        return rows

    except Exception as e:
        print(f"Error fetching details: {e}")
        return []

async def save_to_csv(data):
    if not data:
        print("No data to save.")
        return

    keys = data[0].keys()
    
    try:
        with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(data)
        print(f"Successfully saved schedule to {os.path.abspath(OUTPUT_FILE)}")
    except Exception as e:
        print(f"Error saving CSV: {e}")

async def main():
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("--- Schedule Exporter ---")
        
        # 1. Find the Schedule ID
        schedule_id = await fetch_schedule_id(client)
        if not schedule_id:
            return

        # 2. Fetch and Enrich Data
        data = await fetch_schedule_details(client, schedule_id)
        
        # 3. Save to CSV
        await save_to_csv(data)

if __name__ == "__main__":
    asyncio.run(main())
