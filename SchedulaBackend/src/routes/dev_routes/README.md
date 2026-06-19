# Development Routes

⚠️ **WARNING: FOR DEVELOPMENT ONLY - DO NOT ENABLE IN PRODUCTION** ⚠️

## Overview

This directory contains FastAPI routes for direct database CRUD operations. These routes are intended **strictly for development and testing purposes** and should never be exposed in production environments.

## Enabling Dev Routes

Add to your `.env` file:

```bash
enable_dev_routes=true
```

Or set the environment variable (case-insensitive):

```bash
ENABLE_DEV_ROUTES=true
```

When enabled, all dev routes will be available under the `/dev` prefix and a warning will be printed on startup.

## Available Routes

### Users (`/dev/users`)

- `POST /dev/users/` - Create user
  - Requires: `user_id`, `user_name`, `first_name`, `last_name`, `email`, `role`, `department_id`
  - Note: `user_internal_id` is internal to DB and not returned.
- `GET /dev/users/{user_name}` - Get user by `user_name` (frontend identifier)
- `GET /dev/users/email/{email}` - Get user by email
- `GET /dev/users/` - List all users
- `PATCH /dev/users/{user_name}` - Update user fields by `user_name`
  - Requires: Only fields to update (partial update)
    - `first_name`, `last_name`, `email`, `role`, `department_id`
- `DELETE /dev/users/{user_name}` - Delete user by `user_name`

**Notes:**
- All endpoints use `user_name` as the public identifier for frontend interactions.
- `user_internal_id` is used internally in the database and never returned in responses.
- Notification settings (`phone_num`, `telegram_chat_id`, `telegram_token`, `telegram_enabled`, `email_enabled`) live in the `user_notifications` table and are NOT accepted or returned by these routes. Manage them via [`/dev/user-notifications/`](#user-notifications-devuser-notifications) instead.


### Courses (`/dev/courses`)

- `POST /dev/courses/` – Create course  
  - Requires:`course_number`, `course_name`, `department_id`, `degree_level`,`credit_points`
  - Note: Internal `course_id` is not exposed.
- `GET /dev/courses/{course_number}` – Get course by course number
- `GET /dev/courses/{course_name}` - Get course by course name
- `GET /dev/courses/` – List all courses
- `GET /dev/courses/department/{department_id}` – List courses by department
- `GET /dev/courses/degree_level/{degree_level}` - List courses by degree level
- `GET /dev/courses/cretid_points/{credit_points}` - List courses by credit_points
- `PATCH /dev/courses/{course_internal_id}` – Update course
- `DELETE /dev/courses/{course_internal_id}` – Delete course

**Notes:**  
- `course_number` is the public identifier.  
- Internal `course_id` stays hidden  


### Course Offering (`/dev/course-offering`)

- `POST /dev/course-offering/` – Create course offering  
  - Requires: `course_number` (FK), `academic_year`, `semester`, `group_number`
  - Optional: `cohorts` (array of objects with `target_department_id` and `target_year_level`)
  - Note: `offering_id` is internal PK
- `GET /dev/course-offering/{offering_id}` – Get course offering by internal ID (includes cohorts array)
- `GET /dev/course-offering/` – List all course offerings (each includes cohorts array)
- `GET /dev/course-offering/course/{course_number}` – List offerings for a specific course
- `GET /dev/course-offering/year/{academic_year}` – List offerings by academic year
- `GET /dev/course-offering/year/{academic_year}/semester/{semester}` – List offerings for year+semester
- `GET /dev/course-offering/cohort/{department_id}/{year_level}/{academic_year}/{semester}` – List offerings for a specific cohort
- `GET /dev/course-offering/lookup/{course_number}/{academic_year}/{semester}/{group_number}`  
  – Get a specific offering by full key (course/year/semester/group)
- `PATCH /dev/course-offering/{offering_id}` – Update offering (core fields only, not cohorts)
- `DELETE /dev/course-offering/{offering_id}` – Delete offering (cohorts cascade delete)

**Notes:**  
- `offering_id` is the internal numeric identifier
- Each offering can target multiple cohorts (many-to-many relationship)
- Cohorts are stored in the separate `offering_cohorts` table
- Response format includes `cohorts` array with each cohort's `cohort_id`, `target_department_id`, and `target_year_level`  


### Lecturer Courses (`/dev/lecturer-courses`)

- `POST /dev/lecturer-courses/` - Create/update lecturer-course link
  - Requires: `lecturer_internal_id` (FK), `offering_id` (FK), `role`
  - Note: `Lecturer_course_id` is internal PK
- `GET /dev/lecturer-courses/` – List all assignments
- `GET /dev/lecturer-courses/lecturer/{lecturer_internal_id}` – List by lecturer
- `GET /dev/lecturer-courses/offering/{offering_id}` – List by course offering
- `GET /dev/lecturer-courses/course/{course_id}` - List lecturers for course
- `GET /dev/lecturer-courses/role/{role}` – List by role
- `PATCH /dev/lecturer-courses/{lecturer_course_id}` – Update assignment (partial)
- `DELETE /dev/lecturer-courses/{lecturer_course_id}` – Delete assignment


### Semesters (`/dev/semesters`)

- `POST /dev/semesters/` - Create semester
  - Requires: `semester_year`, `semester_number`, `semester_start_date`, `semester_end_date`,
  `constraint_start_date`, `constraint_end_date`, `change_period_start`, `change_period_end`,
  `status`,
- `GET /dev/semesters/{year}/{number}` - Get semester
- `GET /dev/semesters/` - List all semesters
- `PATCH /dev/semesters/{year}/{number}/status` - Update semester status

### Constraints (`/dev/constraints`)

- `POST /dev/constraints/` – Create constraint
  - Requires: `lecturer_internal_id` (FK), `schedule_id` (FK), `semester_year` (FK), `semester_number` (FK), `raw_text`,
    `structured_rules` (JSONB)
  - Note: constraints_id is internal PK
  - Note: last update is automatically computes in the db
- `GET /dev/constraints/` – List all
- `GET /dev/constraints/lecturer/{lecturer_internal_id}` – List by lecturer
- `GET /dev/constraints/semester/{semester_year}/{semester_number}` – List by semester
- `GET /dev/constraints/schedule/{schedule_id}` – List by schedule
- `GET /dev/constraints/lecturer/{lecturer_internal_id}/latest` – Get latest constraint for lecturer
- `PATCH /dev/constraints/{constraints_id}` – Update constraint (partial)
- `DELETE /dev/constraints/{constraints_id}` – Delete constraint

### Breaking Constraints (`/dev/breaking-constraints`)

- `POST /dev/breaking-constraints/` – Create breaking constraint
  - Requires: `constraints_id` (FK), `atomic_constraint_index`, `semester_year` (FK), `semester_number` (FK)
  - Note: `breaking_id` is internal PK, `is_seen` defaults to False
- `GET /dev/breaking-constraints/{breaking_id}` – Get breaking constraint by ID with details
- `GET /dev/breaking-constraints/semester/{semester_year}/{semester_number}` – List by semester
  - Optional: `unseen_only=true` to filter to unseen constraints only
- `PATCH /dev/breaking-constraints/{breaking_id}/mark-seen` – Mark a breaking constraint as seen
- `PATCH /dev/breaking-constraints/semester/{semester_year}/{semester_number}/mark-all-seen` – Mark all breaking constraints for a semester as seen
- `DELETE /dev/breaking-constraints/{breaking_id}` – Delete breaking constraint
- `DELETE /dev/breaking-constraints/semester/{semester_year}/{semester_number}` – Clear all breaking constraints for a semester

### Schedules (`/dev/schedules`)

- `POST /dev/schedules/` - Create schedule
  - Requires: `semester_year` (FK), `semester_number` (FK), `is_draft`,`is_published`,
- `GET /dev/schedules/{schedule_id}` - Get schedule by ID
- `GET /dev/schedules/semester/{year}/{number}` - List schedules by semester
- `PATCH /dev/schedules/{schedule_id}` - Update schedule
- `DELETE /dev/schedules/{schedule_id}` - Delete schedule

### Courses Schedules (`/dev/courses-schedules`)

- `POST /dev/course-schedules/` – Create course session
  - Requires: `offering_id` (FK), `lecturer_internal_id` (FK), `schedule_id` (FK), `day_of_week`, `start_time`, `end_time`
  - Note: session_id is internal PK
- `GET /dev/course-schedules/` – List all
- `GET /dev/course-schedules/offering/{offering_id}` – List by offering
- `GET /dev/course-schedules/lecturer/{lecturer_internal_id}` – List by lecturer
- `GET /dev/course-schedules/schedule/{schedule_id}` – List by schedule
- `GET /dev/course-schedules/day/{day_of_week}` – List by day
- `GET /dev/course-schedules/start_time/{start_time}` – List by start time
- `GET /dev/course-schedules/end_time/{end_time}` – List by end time
- `PATCH /dev/course-schedules/{session_id}` – Update session (partial)
- `DELETE /dev/course-schedules/{session_id}` – Delete session

### Schedule Approvals (`/dev/schedule-approvals`)

- `POST /dev/schedule-approvals/` – Create approval
  - Requires: `schedule_id` (FK), `lecturer_internal_id` (FK),`status`
  - Note: scheapprov_id is internal PK
- `GET /dev/schedule-approvals/` – List all
- `GET /dev/schedule-approvals/lecturer/{lecturer_internal_id}` – List by lecturer
- `GET /dev/schedule-approvals/schedule/{schedule_id}` – List by schedule
- `GET /dev/schedule-approvals/schedule/{schedule_id}/lecturer/{lecturer_internal_id}` – List by schedule+lecturer
- `GET /dev/schedule-approvals/status/{status}` – List by status
- `PATCH /dev/schedule-approvals/{scheapprov_id}` – Update approval (partial)
- `DELETE /dev/schedule-approvals/{scheapprov_id}` – Delete approval

### Fairness Reports (`/dev/fairness-reports`)

- `POST /dev/fairness-reports/` - Create report
  - Requires: `schedule_id` (FK), `lecturer_internal_id` (FK),`score`, `fullfilled_constraints_json` (JSONB),`broken_constraints_json` (JSONB)
  - Note: report_id is internal PK
- `GET /dev/fairness-reports/{report_id}` - Get report by ID
- `GET /dev/fairness-reports/schedule/{schedule_id}` - List reports for schedule
- `DELETE /dev/fairness-reports/{report_id}` - Delete report

### Solver Runs (`/dev/solver-runs`)

- `POST /dev/solver-runs/` – Create solver run
  - Requires: `semester_year` (FK), `semester_number` (FK)
  - Note: `run_id` is internal PK
- `GET /dev/solver-runs/` – List all solver runs
- `GET /dev/solver-runs/{run_id}` – Get solver run by ID
- `GET /dev/solver-runs/semester/{year}/{number}` – Get the latest solver run for a specific semester
- `PUT /dev/solver-runs/{run_id}` – Update solver run
  - Requires: `status` (must be 'solved' or 'failed')
  - If status is 'solved': `schedule_id` is required
  - If status is 'failed': optional `broken_constraints` (array)
- `DELETE /dev/solver-runs/{run_id}` – Delete solver run

**Notes:**  
- Tracks solver execution runs per semester
- Status can be 'pending', 'solving', 'solved', or 'failed'
- Links to schedules when successfully solved

### User Notifications (`/dev/user-notifications`)

CRUD for the `user_notifications` table (phone, Telegram link, email/Telegram toggles).
This is the canonical place to set notification settings for a user; the
`/dev/users/` routes intentionally do not accept these fields.

- `GET /dev/user-notifications/` – List all user notification rows
- `GET /dev/user-notifications/{user_internal_id}` – Get notification settings by user
- `POST /dev/user-notifications/` – Create or update notification settings for a user
  - Requires: `user_internal_id`
  - Optional: `phone_num` (E.164, e.g. `+972501234567`), `telegram_chat_id`, `telegram_token`, `telegram_enabled`, `email_enabled`
- `DELETE /dev/user-notifications/{notification_id}` – Delete by notification row ID
- `POST /dev/user-notifications/clear-telegram-data` – Clear all users' `telegram_chat_id` and `telegram_token`

**Notes:**
- `clear-telegram-data` is intended for development/testing resets only
- Each user has at most one row (UNIQUE on `user_internal_id`); POST acts as upsert

### Dashboard (`/dev/dashboard`)

- `GET /dev/dashboard/current_semester` – Get the current active semester
  - Returns: `semester_year` and `semester_number` of the currently active semester based on date and status

**Notes:**  
- Helper endpoint for dashboard views
- Returns 404 if no active semester is found

### Telegram Webhook (`/dev/telegram-webhook`)

- `POST /dev/telegram-webhook/set` – Set Telegram webhook at runtime
  - Requires: `public_url` (base URL from cloudflared or named tunnel)
  - Optional: `secret_token`
  - Behavior: delegates to `notification_service` internal webhook set endpoint
- `POST /dev/telegram-webhook/delete` – Delete current Telegram webhook at runtime
  - Optional query param: `drop_pending_updates` (default `false`)
  - Behavior: delegates to `notification_service` internal webhook delete endpoint

### Period Notifications (`/dev/period-notifications`)

- `POST /dev/period-notifications/preview` – Build title/body for a period transition message without sending
- `POST /dev/period-notifications/send` – Manually send a period transition notification to explicit recipients

Expected payload fields:

- `semester_year`, `semester_number`
- `period_type`: `constraint`, `change`, or `status`
- `transition_type`: `start`, `ending_soon`, `ended`, or `changed`
- optional `warning_hours`, `transition_date`, `old_status`, `new_status`
- `recipient_user_ids` (required for send route)

## API Documentation

When dev routes are enabled, visit `/docs` to see interactive Swagger documentation for all endpoints.

## Security Notes

1. **Never enable in production** - These routes bypass all authentication and authorization
2. **Direct database access** - No validation beyond basic type checking
3. **Dangerous operations** - Allows deletion and modification of any data
4. **No audit logging** - Changes made through these routes won't be tracked

## Example Usage

```bash
# ---------------------------
# Users
# ---------------------------

# Create user (no notification fields here)
curl -X POST "http://localhost:8000/dev/users/" \
     -H "Content-Type: application/json" \
     -d '{
           "user_id": "123456789",
           "user_name": "johndoe",
           "first_name": "John",
           "last_name": "Doe",
           "email": "john@example.com",
           "role": "L",
           "department_id": 10
         }'

# Get user by user_name
curl -X GET "http://localhost:8000/dev/users/johndoe"

# Get user by email
curl -X GET "http://localhost:8000/dev/users/email/john@example.com"

# List all users
curl -X GET "http://localhost:8000/dev/users/"

# Update user
curl -X PATCH "http://localhost:8000/dev/users/johndoe" \
     -H "Content-Type: application/json" \
     -d '{
           "first_name": "Jonathan",
           "role": "S"
         }'

# Delete user
curl -X DELETE "http://localhost:8000/dev/users/johndoe"

# ---------------------------
# User Notifications
# ---------------------------

# Set / upsert notification settings for a user (use the user_internal_id from /dev/users)
curl -X POST "http://localhost:8000/dev/user-notifications/" \
     -H "Content-Type: application/json" \
     -d '{
           "user_internal_id": 42,
           "phone_num": "+972501234567",
           "telegram_enabled": true,
           "email_enabled": true
         }'

# Get notification settings for a user
curl -X GET "http://localhost:8000/dev/user-notifications/42"

# List all notification rows
curl -X GET "http://localhost:8000/dev/user-notifications/"

# Delete a notification row by notification_id
curl -X DELETE "http://localhost:8000/dev/user-notifications/7"

# Clear telegram links/tokens for ALL users (dev reset)
curl -X POST "http://localhost:8000/dev/user-notifications/clear-telegram-data"

# ---------------------------
# Courses
# ---------------------------

# Create course
curl -X POST "http://localhost:8000/dev/courses/" \
     -H "Content-Type: application/json" \
     -d '{
           "department_id": 5,
           "degree_level": 1,
           "course_number": 101,
           "course_name": "Algorithms",
           "credit_points": 4
         }'

# Get course by course_number
curl -X GET "http://localhost:8000/dev/courses/101"

# Get course by course_name
curl -X GET "http://localhost:8000/dev/courses/Algorithms"

# List all courses
curl -X GET "http://localhost:8000/dev/courses/"

# List courses by department
curl -X GET "http://localhost:8000/dev/courses/department/5"

# List courses by degree level
curl -X GET "http://localhost:8000/dev/courses/degree_level/1"

# List courses by credit points
curl -X GET "http://localhost:8000/dev/courses/credit_points/4"

# Update course
curl -X PATCH "http://localhost:8000/dev/courses/101" \
     -H "Content-Type: application/json" \
     -d '{
           "course_name": "Advanced Algorithms",
           "credit_points": 5
         }'

# Delete course
curl -X DELETE "http://localhost:8000/dev/courses/101"

# ---------------------------
# Solver Runs
# ---------------------------

# Create solver run
curl -X POST "http://localhost:8000/dev/solver-runs/" \
     -H "Content-Type: application/json" \
     -d '{
           "semester_year": 2025,
           "semester_number": 1
         }'

# Get all solver runs
curl -X GET "http://localhost:8000/dev/solver-runs/"

# Get solver run by ID
curl -X GET "http://localhost:8000/dev/solver-runs/1"

# Get latest solver run for semester
curl -X GET "http://localhost:8000/dev/solver-runs/semester/2025/1"

# Update solver run (mark as solved)
curl -X PUT "http://localhost:8000/dev/solver-runs/1" \
     -H "Content-Type: application/json" \
     -d '{
           "status": "solved",
           "schedule_id": 123
         }'

# Update solver run (mark as failed)
curl -X PUT "http://localhost:8000/dev/solver-runs/1" \
     -H "Content-Type: application/json" \
     -d '{
           "status": "failed",
           "broken_constraints": ["constraint1", "constraint2"]
         }'

# Delete solver run
curl -X DELETE "http://localhost:8000/dev/solver-runs/1"

# ---------------------------
# Dashboard
# ---------------------------

# Get current active semester
curl -X GET "http://localhost:8000/dev/dashboard/current_semester"

```

## Disabling for Production

Ensure `enable_dev_routes` is:

- Not set in production environment variables
- Set to `false` or removed from production `.env` files
- Confirmed disabled via logs (no warning message on startup)
