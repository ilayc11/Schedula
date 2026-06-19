# ⚙️ Secretary/Admin API Reference (Setup & Semesters)

This document outlines the core API endpoints for administrative management in the Schedula Backend. All endpoints listed in this section are **protected** and require a valid JWT with the **Secretary (`S`)** role.

**The base path for these endpoints is assumed to be `/secretary`.**

## 1. 🛡️ Security & Authentication Architecture

The system employs a centralized security layer to ensure data integrity and restricted access to administrative functions.

**1.1. Mandatory Authorization Header**

All administrative requests must be authenticated using the **HTTP Bearer Token** scheme.

  * **Action:** Include the JWT token obtained from the `/auth/login` endpoint in every request.

  * **Format:** `Authorization: Bearer <your_access_token>`

**1.2. Role-Based Access Control (RBAC) Middleware**

Access is strictly governed by the `AuthenticationMiddleware`. 
This layer automatically intercepts requests based on route prefixes:

  * **Prefix Filtering:** Any request starting with `/secretary/*` is flagged as a "Secretary-Only" route.

  * **Role Verification:** The system extracts the `role` claim from the 
decrypted JWT payload. It specifically looks for the **'S'** (Secretary) role.

  * **Automatic Enforcement: * Success:** If the role is `'S'`, 
the middleware populates `request.state` with `user_internal_id` and `user_role`
for use by the endpoint.

    * **Role Mismatch:** If a valid user with a different role 
    (e.g., Lecturer 'L') attempts access, the system returns a 403 Forbidden error
    with the message: *"User does not have Secretary privileges"*.

    * **Token Failure:** If the token is missing, expired, 
    or malformed, the system returns a 401 Unauthorized error.

**1.3. Internal Request State**

Once authorized, the following context is available to all secretary endpoints 
via the `request.state` object:

  * `user_internal_id:` The database primary key of the secretary performing the action (used for Audit Logs).

  * `user_role:` Always **'S'** within this context.

  * `user_payload:` The full decoded JWT for advanced metadata requirements.

---

## 2. 💾 Initial Data Loading (src/routes/external/secretary/setup.py)

These endpoints are used to populate the system with data from Excel files. The process is divided into two stages: Static Data (one-time setup) and Semester Assignments (recurring every semester).

**Notes**
- The initial data endpoint is for starting the system (should not run all the time)
- The load assignment is required each new semester
#### The workflow for new semester:
- (Optional) If there are new lecturers add them to the DB (using the load initial data endpoint)
- Must: Add new semester data (using the semester screen in front page)
- Must: Upload files for assignments for the specific semester (using the load assignment endpoint)

### 2.1. Load Initial Data

Loads semester-independent data: Users (lecturers) and Courses.
***This must be run once before uploading the system.***

Notification settings (`phone_num`, telegram, etc.) are **not** seeded by
this endpoint — they live in the `user_notifications` table and are managed
separately. Secretaries are not created here either; create them through
the standard user flow.

| Property | Details |
| :--- | :--- |
| **Method** | `POST` |
| **Endpoint** | `/secretary/setup/load_data` |
| **Success Status** | `200 OK` (Returns status and count of loaded items) |
| **Error Status** | `400 Bad Request` (File/format error), `403 Forbidden` |

#### Request Body (Multipart/form-data)

| Field                 | Type           | Description                                                                                                                            |
|:----------------------|:---------------|:---------------------------------------------------------------------------------------------------------------------------------------|
| `lecturers_dedu_file` | `File` (XLSX)  | Slim deduplicated lecturer file: identity columns only (`USER_ID`, `ID_NUMBER`, `FIRST_NAME`, `LAST_NAME`, `EMAIL`, `DEPARTMENT`).      |
| `courses_file`        | `File` (XLSX)  | Courses file (`DEPARTMENT`, `DEGREE_LEVEL`, `COURSE`, `NAME`, `CREDIT_POINTS`, optional `Cohort_year`).                                  |

#### Response Example

```json
{
  "status": "success",
  "users_loaded": 150,
  "courses_loaded": 25
}
```

---

### 2.2 Load Semester Assignments

Loads data specific to a semester: Course Offerings, Offering Cohorts, and
Lecturer-Course links. Requires `/load_data` to have been run first so users
and courses already exist; user FKs are resolved by DB lookup rather than
re-insertion.

| Property | Details                                                               |
| :--- |:----------------------------------------------------------------------|
| **Method** | `POST`                                                                |
| **Endpoint** | `/secretary/setup/load_assignments`                                   |
| **Success Status** | `200 OK`                                                              |
| **Error Status** | `400 Bad Request` (Semester missing/ invalid format), `403 Forbidden` |

#### Request Body (Multipart/form-data)

| Field            | Type           | Description                                                                                                                                                   |
|:-----------------|:---------------|:--------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `lecturers_file` | `File` (XLSX)  | Full lecturer file with assignment columns (`USER_ID`/`ID_NUMBER`, `DEPARTMENT`, `COURSE`, `DEGREE_LEVEL`, `GROUP_NUMBER`, `YEAR`, `SEMESTER`, ...).            |
| `courses_file`   | `File` (XLSX)  | Courses file (cohorts are read from this file's `Cohort_year` column).                                                                                         |

#### Semester Validation Rule

Before processing, the system checks the academic year and semester
extracted from the lecturer file:
- If the semester exists in the DB: processing continues.
- If the semester is missing: returns `400 Bad Request` with the message
  `"Semester X/Y not found in DB. Please create it first."`

#### Response Example

```json
{
  "status": "success",
  "offerings_loaded": 30,
  "lecturer_courses_loaded": 45
}
```

---

### 2.3 Test the mapping (no DB writes)

| Property | Details |
| :--- | :--- |
| **Method** | `POST` |
| **Endpoint** | `/secretary/setup/load_data_test` |
| **Success Status** | `200 OK` |

Same form fields as `/load_assignments` (`lecturers_file`, `courses_file`).
Runs the full mapping pipeline but writes the result tables to
`/tmp/test_output.xlsx` instead of the DB, so you can inspect what would
have been inserted.

---

## 3. 📚 Semester Management (src/routes/external/secretary/semesters.py)

These endpoints allow the Secretary to define, update, and view academic semesters.
### 3.1. Create New Semester

Creates a new academic semester record. The system returns the full object as saved in the DB.

| Property | Details |
| :--- | :--- |
| **Method** | `POST` |
| **Endpoint** | `/secretary/semesters/` |
| **Success Status** | **`201 Created` (Returns full `Semester` object)** |
| **Error Status** | `400 Bad Request` (Invalid dates/duplicate key), `403 Forbidden` |

#### Request Body (`SemesterCreate`)

| Field | Type | Description |
| :--- | :--- | :--- |
| `semester_year`, `semester_number` | `integer` | Unique key identifying the semester. |
| `semester_start_date`, `semester_end_date` | `date` | Actual start and end dates of the semester. |
| ... | ... | ... |

#### Response Example (201 Created)

```json
{
  "semester_year": 2026,
  "semester_number": 1,
  "semester_start_date": "2026-10-01",
  "semester_end_date": "2027-01-31",
  "constraint_start_date": "2026-09-15",
  "constraint_end_date": "2026-10-15",
  "change_period_start": "2026-10-01",
  "change_period_end": "2026-10-14",
  "status": "SET"
}
```
---

### 3.2. Update Specific Semester Details

Updates any field (dates or status) for an existing semester defined by its year and number.

| Property | Details                                                     |
| :--- |:------------------------------------------------------------|
| **Method** | `PUT`                                                       |
| **Endpoint** | `secretary/semesters/{semester_year}/{semester_number}`     |
| **Success Status** | `200 OK` (Returns full updated Semester object)             |
| **Error Status** | `400 Bad Request` (Invalid data/no fields), `404 Not Found` |

#### Path Parameters

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `semester_year`, `semester_number` | `integer` | The unique composite key of the semester. |

#### Request Body (`SemesterUpdate`)

| Field | Type | Description |
| :--- | :--- | :--- |
| Any field from `SemesterCreate` | `type (Optional)` | Fields to update (e.g., `"status": "PUB"`). |

#### Response Example (200 OK)
```json
{
  "semester_year": 2026,
  "semester_number": 1,
  "semester_start_date": "2026-10-01",
  "semester_end_date": "2027-01-31",
  "constraint_start_date": "2026-09-15",
  "constraint_end_date": "2026-10-15",
  "change_period_start": "2026-10-01",
  "change_period_end": "2026-10-14",
  "status": "PUB"
}
```
---

### 3.3. Get Specific Semester Details

Retrieves all configuration details for a single semester.

| Property | Details |
| :--- | :--- |
| **Method** | `GET` |
| **Endpoint** | `/secretary/semesters/{semester_year}/{semester_number}` |
| **Success Status** | `200 OK` (Returns single `Semester` object) |
| **Error Status** | `404 Not Found` |

#### Path Parameters

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `semester_year`, `semester_number` | `integer` | The unique composite key of the semester. |

---

### 3.4. Get All Semesters

Retrieves a list of all semesters configured in the system, usually sorted newest first.

| Property | Details |
| :--- | :--- |
| **Method** | `GET` |
| **Endpoint** | `/secretary/semesters/all` |
| **Success Status** | `200 OK` (Returns **List** of `Semester` objects) |

---

## 4. 🗓️ Schedule Management (src/routes/external/secretary/schedules.py)

These endpoints allow the Secretary to initiate the CSP solver, view schedules, and manage schedule include add manually schedule to courses.

### 4.1. Create Schedule and Trigger CSP Solver

Creates (or reuses) a draft schedule record, creates a solver run record, and publishes a request message to **RabbitMQ** to initiate the CSP solver run in the background.

| Property | Details                                                     |
| :--- |:------------------------------------------------------------|
| **Method** | `POST`                                                      |
| **Endpoint** | `/secretary/schedules/publish_request`                      |
| **Success Status** | **`202 Accepted`** (Returns created or reused `Schedule` object)      |
| **Note** | The `202` status indicates background processing (CSP run). |

#### Request Body (`ScheduleCreate`)

| Field | Type | Description |
| :--- | :--- | :--- |
| `semester_year`, `semester_number` | `integer` | The semester to generate a schedule for. |
| `is_draft` | `boolean (Optional)` | `True` if starting a new draft (Default `True`). |

#### What This Endpoint Does:
1. Looks for an existing **empty draft** for the semester (a draft with no
   sessions in `courses_schedules`, e.g., left over from a previous failed
   run). If found, that row is reused; otherwise a new schedule record is
   inserted. This keeps the `schedule_id` returned to the caller stable
   across retries and prevents empty drafts from accumulating.
2. Creates a solver run record to track the processing
3. Publishes a message to RabbitMQ (`constraints_request_queue`) containing:
   - `semester_year` and `semester_number`
   - `run_id` (for tracking the solver execution)
   - `schedule_id` (link to the reused or newly created schedule)
   - `trigger_type`: "manual"

The solver honors the `schedule_id` in the message: when the run completes,
the sessions of the new solution are written to that exact `schedule_id`,
so `GET /secretary/schedules/{schedule_id}/details` and the dashboard's
"latest schedule" view reflect the current solution without indirection.

#### Response Example (202 Accepted)
```json
{
  "schedule_id": 15,
  "semester_year": 2027,
  "semester_number": 1,
  "is_draft": true,
  "is_published": false,
  "created_at": "2026-10-01T10:00:00",
  "last_update": "2026-10-01T10:00:00",
  "published_at": null
}
```

---

### 4.2. Update Schedule Metadata (Draft/Publish Status)

Updates metadata like `is_draft`, `is_published`, and `published_at` for an existing schedule.

| Property | Details                                           |
| :--- |:--------------------------------------------------|
| **Method** | `PUT`                                             |
| **Endpoint** | `/secretary/schedules/{schedule_id}`              |
| **Success Status** | `200 OK` (Returns full updated `Schedule` object) |

#### Path Parameter

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `schedule_id` | `integer` | The ID of the schedule to update. |

#### Request Body (`ScheduleUpdate`)

| Field | Type | Description |
| :--- | :--- | :--- |
| `is_draft`, `is_published` | `boolean (Optional)` | New status flags. |
| `published_at` | `datetime (Optional)` | Timestamp of publication. |

---

### 4.3. Get Schedule Status (Metadata)

Retrieves the `Schedule` object metadata (timestamps, draft/published status) for a specific ID.

| Property | Details |
| :--- | :--- |
| **Method** | `GET` |
| **Endpoint** | `secretary/schedules/{schedule_id}/status` |
| **Success Status** | `200 OK` (Returns single `Schedule` object) |

---

### 4.4. Get Detailed Schedule View (All Sessions)

Retrieves all course sessions scheduled under a specific `schedule_id`, including lecturer, course name, group number, and target cohort information. This endpoint also fetch all the constraints and breaking constraints for this specific schedule.

| Property | Details |
| :--- | :--- |
| **Method** | `GET` |
| **Endpoint** | `secretary/schedules/{schedule_id}/details` |
| **Success Status** | `200 OK` (Returns **List** of `ScheduleSessionDetails` models) |

#### Path Parameter

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `schedule_id` | `integer` | The ID of the schedule to retrieve. |

#### Query Parameters

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `day_of_week` | `integer (Optional)` | Filter by a specific day (1-6). |
| `lecturer_name` | `string (Optional)` | Filter by lecturer's full or partial name. |
| `group_number` | `integer (Optional)` | Filter by course group number. |

#### Response Model (`ScheduleSessionDetails`)

Each session includes:
- **Session Details**: `session_id`, `day_of_week`, `start_time`, `end_time`
- **Course Information**: `course_name`, `course_number`, `offering_id`, `group_number`
- **Lecturer Information**: `lecturer_name`
- **Semester Context**: `semester_year`, `semester_number`, `schedule_id`
- **Target Cohorts** (`cohorts`): Array of cohort objects, each containing:
  - `target_department_id`: Department ID this course offering targets
  - `target_year_level`: Year level (1-4) this course offering targets
- **Lecturer Constraints**: A list of constraints per lecturer for this schedule. Each constraint entry includes `structured_rules`, `is_breaking`, `is_manually_edited`, and `original_raw_text` so the UI can show whether a secretary edited the constraint and what the lecturer's original text was.

**Note**: Each course offering can target multiple cohorts (e.g., shared courses across departments or year levels).

---

### 4.5 Get Offerings Distribution (Scheduled vs. Unscheduled)

Returns two separate lists for a specific schedule:  
those who already have scheduled and those who still waiting for one.

| Property | Details |
|--------|--------|
| **Method** | GET |
| **Endpoint** | `/secretary/schedules/{schedule_id}/offerings-distribution` |
| **Success Status** | `200 OK` |

#### Query Parameters

| Parameter | Type | Required | Description |
|----------|------|----------|-------------|
| `semester_year` | int | Yes | Academic year of the semester |
| `semester_number` | int | Yes | Semester number |

#### Response Structure

The response consists of two main arrays.  
- **scheduled**  
  List of offerings that already have scheduled sessions.
  Each item have session details: **session_id**, **day_of_week**, **start_time**, **end_time** .

- **unscheduled**  
  List of offerings that **do not yet have a session record** for this schedule.

| Field | Type | Description                                                  |
|------|------|--------------------------------------------------------------|
| `scheduled` | Array[Object] | Offerings that have an assigned slot in `courses_schedules`. |
| `unscheduled` | Array[Object] | Offerings that don't have schedule yet.                      |
| `total_count` | integer | Total number of offerings in the semester.                   |
| `scheduled_count` | integer | Number of items in the `scheduled` list.                     |
| `unscheduled_count` | integer | Number of items in the `unscheduled` list.                   |

```
{
    "scheduled": [
        {
            "offering_id": 101,
            "course_name": "Algorithms",
            "lecturer_name": "Dr. Levy",
            "session": {"session_id" ,"day_of_week": 2, "start_time": "10:00", "end_time": "12:00"}
        }
    ],
    "unscheduled": [
        {
            "offering_id": 102,
            "course_name": "Data Structures",
            "lecturer_name": "Prof. Cohen",
            "session": {}
        }
    ],
    "total_count": 2,
    "scheduled_count": 1,
    "unscheduled_count": 1
}
```

---

### 4.6 Create or Update Manual Session (Override)

Creates a new session record or updates an existing one for a specific course offering.

Allows the secretary to **manually place a course in the schedule**, bypassing or overriding automated solver results. Also update the constraints that broke by the manually schedule.

| Property | Details |
|--------|--------|
| **Method** | POST |
| **Endpoint** | `/secretary/schedules/{schedule_id}/sessions` |
| **Success Status** | `201 Created` |

##### Request Body Example

```json
{
  "offering_id": 105,
  "lecturer_internal_id": 101,
  "day_of_week": 2,
  "start_time": "16:00:00",
  "end_time": "18:00:00",
  "breaking_constraint": [
      {
          "constraint_id": 55,
          "semester_year": 2026,
          "semester_number": 1,
          "breaking_atomic_constraints": [{
              "atomic_constraint_index": 0,
              "days": [3],
              "type": "block",
              "time_slot": { "start_hour": 10, "end_hour": 13 }
          }]
      },
  ], 
}
```
---

### 4.7 Delete Scheduled Session

Removes a specific session from the schedule, moving the course back to the **unscheduled list**.

| Property | Details |
|--------|--------|
| **Method** | DELETE |
| **Endpoint** | `/secretary/schedules/{schedule_id}/sessions/{session_id}` |
| **Success Status** | `204 No Content` |

--- 


## 5. Dashboard Endpoints (src/routes/external/secretary/dashboard.py)

These endpoints allow the Secretary to view data about the semester, the statistics on the lecturers and the newest schedule.

### 5.1. Get Active Semester Info
Returns general dates and workflow status for the current active semester.

| Property | Details |
| :--- | :--- |
| **Method** | `GET` |
| **Endpoint** | `/dashboard/semester_info` |
| **Success Status** | `200 OK` (Returns `SemesterBase`) |

---

### 5.2. Get Semester Statistics
Returns dynamic data based on the current semester workflow stage.

| Property | Details |
| :--- | :--- |
| **Method** | `GET` |
| **Endpoint** | `/dashboard/stats` |
| **Success Status** | `200 OK` |

#### Use Case: Constraint Submission Stage (`status: SUB`)
Returns how many lecturers have submitted their constraints and identifies those who haven't.

Response during Constraint Submission (status: SUB)
Focuses on how many lecturers have completed their task.

##### Example Response:
```
JSON
{
    "type": "constraints",
    "total_lecturers": 50,
    "submitted_count": 35,
    "missing_lecturers": [
        {
            "first_name": "Alice",
            "last_name": "Smith",
            "email": "alice@univ.edu"
        }
    ]
}
```

#### Use Case: Schedule Approval Stage (`status: CHA/PUB`)
Returns counts of approvals/rejections and a lists of lecturers who are still pending and have rejected the proposed schedule.

Response during Approval/Published Phase (status: CHA or PUB)
Focuses on schedule acceptance by the faculty.

##### Example Response:

```
JSON
{
    "type": "approvals",
    "schedule_id": 42,
    "approved": 20,
    "rejected": 5,
    "pending": 25,
    "pending_lecturers": [
         {"first_name": "Bob", "last_name": "Jones", "email": "bob@univ.edu", "status": "PEN"}
    ],
    "rejected_lecturers": [
         {"first_name": "John", "last_name": "Doe", "email": "johnd@univ.edu", "status": "REJ"}
    ]
}
```

---

### 5.3 Get Solver Run Status
Retrieves the simplified status of the most recent CSP solver execution for a specific semester. This endpoint allows the frontend to track background processing and display a high-level summary of results or failures.

| Property | Details                                     |
| :--- |:--------------------------------------------|
| **Method** | `GET`                                       |
| **Endpoint** | `secretary/schedules/solver_status`         |
| **Security** | JWT Required (Role: S)                      |
| **Success Status** | `200 OK`                                    |
| **Error Status** | `403 Forbidden`, `500 internal Server Error` |

### Query Parameters

| Parameter       | Type      | Description                    |
|:----------------|:----------|:-------------------------------|
| `semester_year` | `integer` | The academic year (e.g, 2026). |
| `semester_number` | `integer` | The semester index (1,2,3). |

### Solver Statuses (status field)

- pending: The solver is currently calculating a schedule.

- solved: Success! A valid schedule was generated and linked via schedule_id.

- failed: The solver could not find a solution due to conflicts (Broken Constraints).

- none: No solver runs have been initiated for this semester yet.

### Response Structure (Success Example)

| Field                        | Type                  | Description                                            |
|:-----------------------------|:----------------------|:-------------------------------------------------------|
| `run_id`                     | `integer`             | Unique ID for this solver execution.                   |
| `status`                     | `string`              | Current status.                                        |
| `schedule_id`                | `integer / null`      | Link to the generated schedule (if solved).            |
| `broken_constraints_count`        | `integer`             | The total number of constraints that caused a failure. |
| `semeste_year`, `semester_number` | `integer` | the academic data for the semester                     |
#### Example Response: Succeeded (Solved)
```json
{
"run_id": 15,
    "status": "solved",
    "schedule_id": 42,
    "broken_constraints_count": 0,
    "created_at": "2025-12-17T10:30:00Z",
    "completed_at": "2025-12-17T10:30:45Z",
    "semester_year": 2026,
    "semester_number": 1
}
```

### Example Response: Failed (With Conflict Details)

```json
{
  "run_id": 16,
  "status": "failed",
  "schedule_id": null,
  "broken_constraints_count": 2,
  "created_at": "2025-12-17T11:00:00Z",
  "completed_at": "2025-12-17T11:01:20Z",
  "semester_year": 2026,
  "semester_number": 1
}
```

---

## 6. Breaking Constraints Endpoints (src/routes/external/secretary/breaking_constraints.py)

These endpoints allow the Secretary to view data about the constraints that broke the solver.

---

### 6.1. List Breaking Constraints (semester)

Retrieves constraints identified by the solver as "unsolvable" for a specific semester

| Property | Details                                           |
| :--- |:--------------------------------------------------|
| **Method** | `GET`                                             |
| **Endpoint** | `/secretary/breaking-constraints/{year}/{number}` |
| **Query Params** | `unseen_only (boolean, optional`                  |
| **Success Status** | `200 OK` (Returns `SemesterBase`)                 |

> Each row also includes `structured_rules`, `is_manually_edited`, and
> `original_raw_text` from the parent `lecturer_constraints` row, so the UI
> can render the current rules and surface a "manually modified" indicator
> with the lecturer's original text.

---

### 6.2. List Breaking Constraints by Lecturer

Filters conflicts for a specific lecturer to allow targeted resolution.

| Property | Details                                                                  |
| :--- |:-------------------------------------------------------------------------|
| **Method** | `GET`                                                                    |
| **Endpoint** | `/secretary/breaking-constraints/lecturer/{lecturer_id}/{year}/{number}` |
| **Success Status** | `200 OK`                                                                 |

> Same enrichment as 6.1: rows include `structured_rules`,
> `is_manually_edited`, and `original_raw_text`.

#### Example Response:

``` Json
Responses:
        200: {
            "status": "success",
            "data": [
                {
                    "breaking_id": 15,
                    "constraints_id": 42,
                    "breaking_atomic_constraints": [
                        {
                            "atomic_constraint_index": 0,
                            "days": [1],
                            "type": "block",
                            "time_slot": {"start_hour": 8, "end_hour": 10}
                        }
                    ],
                    "semester_year": 2026,
                    "semester_number": 1,
                    "is_seen": false,
                    "lecturer_internal_id": 101,
                    "created_at": "2026-01-20T10:00:00Z"
                }
            ],
            "count": 1
        }
```

---

### 6.3 Mark as Seen

Marks a conflict as "reviewed" by the secretary.

| Property | Details                                                   |
| :--- |:----------------------------------------------------------|
| **Method** | `POST`                                                    |
| **Endpoint** | `/secretary/breaking-constraints/{breaking_id}/mark-seen` |
| **Success Status** | `200 OK` Return the updated constraint                    |

---

### 6.4 Get Unseen Count

Returns the number of breaking constraints yet to be reviewed for a semester.

| Property | Details                                                                          |
| :--- |:---------------------------------------------------------------------------------|
| **Method** | `GET`                                                                            |
| **Endpoint** | `/secretary/breaking-constraints/{semester_year}/{semester_number}/unseen-count` |
| **Success Status** | `200 OK` Return the conut of unseen constraints                                  |

---

### 6.5 Get Specific Breaking Constraint

Retrieves detailed information for a single breaking constraint by its unique ID.

| Property | Details                                         |
| :--- |:------------------------------------------------|
| **Method** | `GET`                                           |
| **Endpoint** | `/secretary/breaking-constraints/{breaking_id}` |
| **Success Status** | `200 OK`  |

---

### 6.6 Mark all as Seen 

Marks all breaking constraints for a specific semester as reviewed in a single operation.

| Property | Details                                                                                        |
| :--- |:-----------------------------------------------------------------------------------------------|
| **Method** | `POST`                                                                                         |
| **Endpoint** | `/secretary/breaking-constraints/{semester_year}/{semester_number}/mark-all-seen`              |
| **Success Status** | `200 OK` (Returns count of updated records)                                                    |

--- 

### 6.7 Get constraints full report

Retrieves a unified report of all lecturer constraints for a specific semester, indicating which were satisfied and which were broken by the solver.

| Property | Details                                         |
| :--- |:------------------------------------------------|
| **Method** | `GET`                                           |
| **Endpoint** | `/secretary/breaking-constraints/{semester_year}/{semester_number}/full-report` |
| **Success Status** | `200 OK` Returns enrich constraints data  |

> Each entry now also carries `structured_rules`, `is_manually_edited`, and
> `original_raw_text` so the UI can render rules and the "manually modified"
> indicator without an extra fetch.

```Json
{
    "status": "success",
    "semester_year": "2026",
    "semester_number": "1",
    "data": [
        {
            "constraints_id": 88,
            "lecturer_id": 42,
            "raw_text": "No classes on Friday",
            "structured_rules": {"atomic_constraints": [/* ... */]},
            "is_broken": true,
            "status": "broken",
            "breaking_details": {
                "breaking_id": 12,
                "breaking_atomic_constraints": [/* ... */]
            },
            "is_manually_edited": false,
            "original_raw_text": null,
            "last_updated": "2026-01-20T10:00:00Z"
        },
        {
            "constraints_id": 89,
            "lecturer_id": 42,
            "raw_text": "Blocks Sunday 08:00-10:00 (hard)",
            "structured_rules": {"atomic_constraints": [/* ... */]},
            "is_broken": false,
            "status": "satisfied",
            "breaking_details": null,
            "is_manually_edited": true,
            "original_raw_text": "Prefer morning slots",
            "last_updated": "2026-01-20T11:30:00Z"
        }
    ],
    "count": 2
}
```

---

## 7. 🛠️ Constraint Management (src/routes/external/secretary/manage_constraints.py)

These endpoints allow the secretary to manually intervene and resolve conflicts by modifying or deleting lecturer constraints.

### 7.1 Search Constraints

Flexible endpoint to find constraints by semester, lecturer, or both.

| Property         | Details                                                          |
|:-----------------|:-----------------------------------------------------------------|
| **Method**       | `GET`                                                            |
| **Endpoint**     | `/secretary/manage_constraints/search`                           |
| **Query Params** | `semester_year`, `semester_number`, `lecturer_id` (all optional) |


### 7.2 Update Constraint Priority (Hard/Soft)

Allows the secretary to "relax" a constraint. 
If an instructor has a "Hard" constraint that breaks the schedule, 
the secretary can change it to "Soft" so the solver can bypass it if necessary.

| Property         | Details                                                   |
|:-----------------|:----------------------------------------------------------|
| **Method**       | `PATCH`                                                   |
| **Endpoint**     | `/secretary/manage_constraints/{constraints_id}/priority` |

#### Request Body

``` JSON
{
  "secretary_override_as_hard": null
}
```

**Values:**
- `true`: Force all atomic constraints to HARD (cannot be relaxed)
- `false`: Force all atomic constraints to SOFT (can be relaxed)
- `null`: Use per-atomic priority from LLM classification

### 7.3. Delete Original Constraint

Deletes the constraint from the database entirely. 
Note: Deleting a source constraint will automatically remove any related 
"Breaking Constraint" records due to database cascade.

| Property         | Details                                          |
|:-----------------|:-------------------------------------------------|
| **Method**       | `DELETE`                                         |
| **Endpoint**     | `/secretary/manage_constraints/{constraints_id}` |
| **Success Status** | `200 OK`                                         |

---

### 7.4. Edit Structured Rules

Replaces the `structured_rules` of an existing lecturer constraint with a
secretary-authored version. Bypasses the LLM pipeline — the secretary is
authoritative.

The constraint is then flagged `is_manually_edited=true`, the lecturer's
**original raw text is preserved on the first edit** (`original_raw_text`,
captured once and never overwritten by later edits), and breaking-constraint
rows tied to this constraint are recomputed against the live schedule.

On success, the endpoint also **auto-enqueues a CSP solver run** for the
constraint's semester (queue: `constraints_request_queue`,
`trigger_type: "manual"`), so the schedule, breaking constraints, and
fairness report all converge to the new rules without a separate
`POST /secretary/schedules/publish_request` call. The enqueue is
best-effort: if RabbitMQ is unreachable the edit still returns `200 OK`
and only logs a warning. Callers can poll
`GET /secretary/schedules/solver_status` to observe the resulting run.

Multiple rapid edits on the same semester are coalesced by the solver's
batching window into a single re-solve.

| Property         | Details                                                            |
|:-----------------|:-------------------------------------------------------------------|
| **Method**       | `PUT`                                                              |
| **Endpoint**     | `/secretary/manage_constraints/{constraints_id}/structured-rules`  |
| **Success Status** | `200 OK` (returns updated `Constraint`)                          |
| **Error Status** | `403 Forbidden`, `404 Not Found`, `422 Unprocessable Entity`       |

#### Path Parameters

| Parameter         | Type      | Description                          |
|:------------------|:----------|:-------------------------------------|
| `constraints_id`  | `integer` | The internal id of the constraint.   |

#### Request Body (`SecretaryStructuredRulesEdit`)

| Field               | Type     | Description                                                                                                      |
|:--------------------|:---------|:-----------------------------------------------------------------------------------------------------------------|
| `structured_rules`  | `object` | Object with `atomic_constraints` array. See validation rules below.                                              |
| `raw_text`          | `string` | Optional new human-readable text. If omitted, the server generates a preview from the rules.                     |

##### Example Request

```json
{
  "structured_rules": {
    "atomic_constraints": [
      {
        "type": "block",
        "days": [1, 2],
        "time_slot": {"start_hour": 8, "end_hour": 10},
        "priority": "hard"
      },
      {
        "type": "preference",
        "days": [3],
        "time_slot": null,
        "priority": "soft"
      }
    ]
  },
  "raw_text": null
}
```

#### Validation rules

For each atomic constraint:
- `type` must be `"block"` or `"preference"`. **Type is locked for surviving
  atomics**: if you keep an atomic at index `i`, its type must match the type
  of the existing atomic at index `i`. New atomics appended to the tail may
  have any valid type.
- `days` must be a non-empty list of unique ints in `1..6`.
- `time_slot` must be either `null` (full day) or
  `{start_hour, end_hour, start_minute?, end_minute?}` with
  `start_hour` in `0..23`, `end_hour` in `0..24`, minutes in `0..59`, and
  `start < end` at minute resolution.
- `priority` must be `"hard"` or `"soft"`.
- The list must contain at least one atomic.
- Duplicate atomics (same type/days/time_slot/priority) are rejected.

If validation fails, the endpoint returns **`422 Unprocessable Entity`** with
a structured error body:

```json
{
  "detail": {
    "status": "error",
    "errors": [
      {
        "path": "atomic_constraints[0].type",
        "message": "type cannot change from 'block' to 'preference'"
      },
      {
        "path": "atomic_constraints[1].time_slot",
        "message": "start_hour must be < end_hour"
      }
    ]
  }
}
```

#### Example Response (200 OK)

```json
{
  "status": "success",
  "data": {
    "constraints_id": 88,
    "lecturer_internal_id": 42,
    "schedule_id": 10,
    "semester_year": 2026,
    "semester_number": 1,
    "raw_text": "Blocks Sunday and Monday 08:00-10:00 (hard). Prefers no classes Tuesday all day (soft)",
    "structured_rules": {
      "atomic_constraints": [
        {"type": "block", "days": [1, 2], "time_slot": {"start_hour": 8, "end_hour": 10}, "priority": "hard"},
        {"type": "preference", "days": [3], "time_slot": null, "priority": "soft"}
      ]
    },
    "secretary_override_as_hard": null,
    "is_manually_edited": true,
    "original_raw_text": "I cannot teach on Sundays before 10:00.",
    "last_updated_at": "2026-05-15T14:00:00Z"
  }
}
```

---

## 8. ⚖️ Fairness Endpoints (src/routes/external/secretary/fairness.py)

These endpoints power the secretary "Fairness Review" page. They report, per lecturer, how many atomic constraints were satisfied vs broken by a schedule, with a hard/soft breakdown and a weighted fairness score.

---

### 8.1. Get Lecturer Fairness Report

Returns per-lecturer atomic-constraint coverage against a schedule for the given semester. By default the endpoint resolves the **latest schedule for the semester** (published if any, else the most recent draft). The optional `schedule_id` query parameter overrides this resolution.

| Property | Details                                                                       |
| :--- |:------------------------------------------------------------------------------|
| **Method** | `GET`                                                                         |
| **Endpoint** | `/secretary/fairness/{semester_year}/{semester_number}`                       |
| **Query Params** | `schedule_id` (integer, optional)                                             |
| **Success Status** | `200 OK`                                                                      |
| **Error Status** | `400 Bad Request` (schedule does not belong to semester), `403 Forbidden`, `404 Not Found` (explicit `schedule_id` does not exist) |

#### Path Parameters

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `semester_year` | `integer` | The academic year (2000–2100). |
| `semester_number` | `integer` | The semester number (1, 2, or 3). |

#### Response Structure

| Field | Type | Description |
| :--- | :--- | :--- |
| `status` | `string` | Always `"success"` on `200`. |
| `semester_year`, `semester_number` | `integer` | Echo of the requested semester. |
| `schedule_id` | `integer / null` | Resolved schedule. `null` when no schedule exists yet. |
| `schedule_status` | `string` | `"published"`, `"draft"`, or `"none"`. |
| `data` | `LecturerFairness[]` | One entry per lecturer (`users.role = 'L'`), even when they have no constraints. |
| `count` | `integer` | Length of `data`. |

Each `LecturerFairness` row contains:

| Field | Type | Description |
| :--- | :--- | :--- |
| `lecturer_internal_id`, `lecturer_name` | `integer`, `string` | Lecturer identity. |
| `courses_count` | `integer` | Distinct course offerings the lecturer is assigned to in the semester. |
| `total_atomics` | `integer` | All atomic rules across the lecturer's constraint rows. |
| `broken_atomics`, `satisfied_atomics` | `integer` | Counts of atomics flagged as broken (via `breaking_constraints`) vs not. |
| `hard_total`, `soft_total` | `integer` | Same total, split by priority. Priority is resolved using `secretary_override_as_hard`; when `NULL`, the atomic's own `priority` is used (default `soft`). |
| `hard_broken`, `soft_broken` | `integer` | Broken atomics split by priority. |
| `fairness_score` | `float` | Weighted score in `[0, 1]`: `(satisfied + 0.5 * soft_broken) / max(total, 1)`. Hard breaks penalise the most. Lecturers with no atomics get `1.0`. |
| `is_fair` | `boolean` | `hard_broken == 0`. |
| `atomic_details` | `AtomicDetail[]` | Per-atomic breakdown for the right-hand UI panel. |

Each `AtomicDetail`:

| Field | Type | Description |
| :--- | :--- | :--- |
| `constraints_id` | `integer / null` | Parent `lecturer_constraints.constraints_id`. |
| `raw_text` | `string / null` | Lecturer's raw text for that parent constraint. |
| `atomic_index` | `integer` | Index inside `structured_rules.atomic_constraints`. |
| `type` | `string / null` | Typically `"block"` or `"preference"`. |
| `days` | `integer[]` | Days targeted (1=Sunday … 6=Friday). |
| `time_slot` | `object / null` | `{start_hour, end_hour, start_minute?, end_minute?}`, or `null` for full-day. |
| `is_hard`, `is_broken` | `boolean` | Resolved priority and whether the solver flagged this atomic as broken. |

#### Behaviour When There Is No Schedule

If `schedule_id` is omitted and no schedule exists for the semester, the endpoint still returns `200 OK` with `schedule_id: null`, `schedule_status: "none"`, and a `data` array containing every lecturer with all counts zeroed (`fairness_score = 1.0`).

#### Example Response (200 OK)

```json
{
  "status": "success",
  "semester_year": 2026,
  "semester_number": 1,
  "schedule_id": 12,
  "schedule_status": "published",
  "data": [
    {
      "lecturer_internal_id": 101,
      "lecturer_name": "Dana Cohen",
      "courses_count": 3,
      "total_atomics": 4,
      "broken_atomics": 1,
      "satisfied_atomics": 3,
      "hard_total": 2,
      "soft_total": 2,
      "hard_broken": 1,
      "soft_broken": 0,
      "fairness_score": 0.75,
      "is_fair": false,
      "atomic_details": [
        {
          "constraints_id": 42,
          "raw_text": "I cannot teach on Mondays 16-20",
          "atomic_index": 0,
          "type": "block",
          "days": [2],
          "time_slot": {"start_hour": 16, "end_hour": 20},
          "is_hard": true,
          "is_broken": true
        }
      ]
    }
  ],
  "count": 1
}
```
