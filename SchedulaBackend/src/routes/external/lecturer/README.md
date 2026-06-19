# Lecturer API Reference (Authentication & Constraints)

This document outlines the API endpoints for lecturers in the system. 

* **Middleware Protection:** All endpoints (except public auth) 
are automatically protected by `AuthenticationMiddleware`.

* **Role Enforcement:** Prefix `/lecturer/` automatically requires the **Lecturer (L)** role.

* **Context:** Authenticated requests automatically populate `request.state` 
with `user_internal_id` and `user_role`.

---

## 1. Authentication Flow (src/routes/auth.py)

The authentication system issues JWT tokens that the Middleware uses to authorize requests.

### 1.1. User Login (Get Access Token)

| Property | Details                             |
| --- |-------------------------------------|
| **Method** | POST                                |
| **Endpoint** | `/auth/login`                       |
| **Security** | Public (Excluded from Middleware)                             |
| **Success Status** | 200 OK (returns LoginSuccess model) |
| **Failure Status** | 404 Not Found, 401 Unauthorized     |

#### Request Body (LoginPayload)

| Field | Type   | Description                    |
| --- |--------|--------------------------------|
| `user_name` | string | Unique username used for login |
| `user_id` | string | User ID 9-digits               |

#### Successful Response (200 OK)

``` JSON 
{
  "message": "Login successful",
  "token": {
    "access_token": "eyJhbG...", 
    "token_type": "bearer",
    "expires_in": 3600,
    "user_data": { "user_name": "jdoe", "role": "L", ... }
  }
}
```
---

### 1.2. User Logout

Clients should discard the JWT locally. The server-side logout is stateless.

| Property | Details |
| --- | --- |
| **Method** | POST |
| **Endpoint** | `/auth/logout` |
| **Success Status** | 200 OK |
| **Description** | Client must discard the stored JWT |

---

## 2. JWT Usage & Client Requirements

**A. Middleware logic**

The `AuthenticationMiddleware` intercepts every request:
  * **Public Access:** Paths starting with: `/auth`, `/docs`, or `/dev` bypass check.
  * **Extraction:** Extracts the token from `Authorization: Bearer <token>`.
  * **Validation:** Decodes the token using `decode_token()` to verify signature 
  and expiration.
  * **RBAC:** If the path starts with `/lecturer`, it verifies the token `role` is `"L"`.
  * **State Injection:** Populates `request.state.user_internal_id` for use in the route handler.

**B. Header Requirement**

For all `/lecturer/*` endpoints, the following header is mandatory:
$$\text{Authorization: Bearer }\langle\text{access_token}\rangle$$

---

## 3. 📅 Constraints Endpoints (src/routes/external/lecturer/constraints.py)

This section details the endpoints used by lecturers to manage their constraints. The system uses a sophisticated two-step workflow:

1) **Preview:** Linguistic processing and text combination (via LLM).

2) **Save:** Conflict resolution (deletion of old records) and database persistence.

* All endpoints require the **Lecturer (`L`) role**.

---
### Constraint Workflow Overview

1) **Text Combination:** If the lecturer already has constraints for the semester, the system linguistically merges the old text with the new input.

2) **Atomization:** The combined text is broken down into "Atomic Constraints" (e.g., "No Mondays" and "Morning preference").

3) **Clarification:** If the input is ambiguous (Stage 0), the system requests clarification.

4) **Conflict Resolution (on Save):** When saving, the system automatically removes all previous constraints for that semester to replace them with the new, unified set.

---

### 3.1. Create/update Constraint

This is the primary entry point. It processes raw text, 
combines it with existing semester data, and returns a structured preview. 

***It does not modify the database.***

| Property | Details                                                         |
| :--- |:----------------------------------------------------------------|
| **Method** | `POST`                                                          |
| **Endpoint** | `/lecturer/constraints/preview`                                 |
| **Security** | Role: L requierd                                                |
| **Success Status** | `200 OK` (Returns `ConstraintModel` or `Clarification Request`) |
| **Error Status** | `400 Bad Request` (LLM/Parsing error), `403 Forbidden`          |

#### Request Body (`ConstraintPreviewPayload`)

| Field | Type | Description |
| :--- | :--- | :--- |
| `raw_text` | `string` | The free text constraint entered by the user. |
| `semester_year` | `integer` | Target semester year. |
| `semester_number` | `integer` | Target semester number (1-3). |

#### Response Example

``` JSON 
{
  "status": "success",
  "data": {
    "lecturer_internal_id": 1,
    "raw_text": "I cannot work Sundays (existing). Also, I prefer mornings on Mondays (new).",
    "structured_rules": {
      "atomic_constraints": [
        {"type": "block", "days": [1], "priority": "hard"},
        {"type": "preference", "days": [2], "time_slot": {"start_hour": 8, "end_hour": 12}, "priority": "soft"}
      ]
    },
    "has_existing": true,
    "existing_constraint_ids": [45]
  }
}
```

---

### 3.2. Save Confirmed Constraint

Saves the previewed constraints to the database. 
This endpoint handles the "Replacement" logic to ensure no duplicate or 
conflicting records exist for the same semester.

| Property | Details                                                           |
| :--- |:------------------------------------------------------------------|
| **Method** | `POST`                                                            |
| **Endpoint** | `/lecturer/constraints/save`                                      |
| **Security** | JWT required, Role: L. **Checks if payload ID matches token ID.** |
| **Success Status** | `201 Created` (Returns created `Constraint` object)               |
| **Error Status** | `400 Bad Request` (DB error), `403 Forbidden` (ID mismatch)       |

#### Request Body (`ConstraintSave`)

The payload must contain the full `ConstraintSavePayload` data received during the preview step, including the approved `structured_rules`.

| Field | Type | Description |
| :--- | :--- | :--- |
| `lecturer_internal_id` | `integer` | **Must match the JWT's internal ID.** |
| `semester_year`, `semester_number` | `integer` | Semester context. |
| `raw_text` | `string` | The original text. |
| **`structured_rules`** | `JSON` | **CRITICAL:** The structured rules approved by the user. |

---

### 3.3. Get My Constraints

Retrieves all constraint history for the authenticated lecturer.

| Property | Details                                        |
| --- |------------------------------------------------|
| **Method** | GET                                            |
| **Endpoint** | `/lecturer/constraints/my_constraitns`         |
| **Success Status** | 200 OK (Returns List of Constraint objects)    |
| **Notes** | Returns an empty array if no constraints exist |

> Each returned constraint also includes `is_manually_edited` (boolean) and
> `original_raw_text` (string or null). When `is_manually_edited` is `true`,
> a secretary has edited the structured rules; the constraint's current
> `raw_text` reflects the edited version, while `original_raw_text` preserves
> the lecturer's original text from before the first secretary edit. These
> fields are read-only for the lecturer.

---

### 3.4. Delete Specific Constraint ID

Deletes a single constraint record.

**NOTE:** If the constraint is in the `breakin_constraints` table, it will automatically be deleted from there too

| Property | Details                                                |
| --- |--------------------------------------------------------|
| **Method** | DELETE                                                 |
| **Endpoint** | `/lecturer/constraints/{constraints_id}`                 |
| **Security** | Verified: User must be the owner of the constraint. |
| **Success Status** | 200 OK (Returns single Constraint object)              |
| **Error Status** | 403 Forbidden (Does not own constraint), 404 Not Found |

#### Path Parameter

| Field | Type | Description |
| --- | --- | --- |
| constraint_id | integer | The internal primary key ID of the constraint. |

---

## 4. 🗓️ Schedule & Approval Endpoints (src/routes/external/lecturer/schedules.py)

These endpoints allow the lecturer to view their schedule and submit their approval/rejection status.

### 4.1. Get Detailed Schedule View (My Schedule)

Returns the lecturer's scheduled sessions for a specific semester, ready for calendar/list display.

| Property | Details |
| :--- | :--- |
| **Method** | `GET` |
| **Endpoint** | `/schedules/my_schedule` |
| **Success Status** | `200 OK` (Returns List of **`ScheduleSessionDetails`** models) |

#### Query Parameters

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `semester_year`, `semester_number` | `integer (Required)` | Semester to query. |
| `day_of_week` | `integer (Optional)` | Filter by a specific day (1=Sun, 6=Fri). |
| `target_department_id` | `integer (Optional)` | Filter sessions by target cohort department. |
| `target_year_level` | `integer (Optional)` | Filter sessions by target cohort year level (1-6). |

#### Response Model (`ScheduleSessionDetails`)

Each session includes:
- Course and session details (`session_id`, `schedule_id`, `day_of_week`, `start_time`, `end_time`)
- Course information (`course_name`, `course_number`, `group_number`)
- Lecturer information (`lecturer_name`)
- Semester context (`semester_year`, `semester_number`)
- **`cohorts`**: Array of target cohorts for this offering, each containing:
  - `target_department_id`: The department this course is offered to
  - `target_year_level`: The year level this course is offered to

---

### 4.2. Submit or Update Schedule Approval

Submits the lecturer's decision (`APP` or `REJ`) for a specific schedule. This uses **UPSERT** logic, allowing the lecturer to change their decision later by sending the same `schedule_id` with a new status.

| Property | Details                                      |
| :--- |:---------------------------------------------|
| **Method** | `POST`                                       |
| **Endpoint** | `lecturer/schedules/approval`                         |
| **Success Status** | `200 OK` (Returns message confirming action) |

#### Request Body (`ScheduleApprovalBase`)

| Field | Type | Description |
| :--- | :--- | :--- |
| `schedule_id` | `integer` | The ID of the schedule/draft being approved/rejected. |
| **`status`** | `string` | **`"APP"`** (Approved) or **`"REJ"`** (Rejected). |
| **Note** | `lecturer_internal_id` is automatically taken from the JWT. |

#### Success Messages

| Status | Message |
| :--- | :--- |
| `APP` | "Thank you for the approval. You will receive an update when the final schedule is published." |
| `REJ` | "You have rejected the schedule. Please submit additional constraints in the constraint entry screen." |

---

### 4.3. Get My Current Approval Status

Returns the current approval status (APP/REJ/PEN) for a specific schedule ID.

| Property | Details                                                                   |
| :--- |:--------------------------------------------------------------------------|
| **Method** | `GET`                                                                     |
| **Endpoint** | `lecturer/schedules/approval/{schedule_id}`                                        |
| **Path Parameter** | `schedule_id`                                                             |
| **Success Status** | `200 OK` (Returns `ScheduleApproval` model)                               |
| **Error Status** | `404 Not Found` (if no explicit record exists for this lecturer/schedule) |


## 5. Dashboard Endpoints (src/routes/external/lecturer/dashboard.py)

These endpoints provide high-level summary data for the lecturer's main dashboard view.

### 5.1. Get Current Active Semester
Retrieves information about the currently active semester, including its processing status and the deadline for constraint submission.

| Property | Details                                               |
| :--- |:------------------------------------------------------|
| **Method** | `GET`                                                 |
| **Endpoint** | `lecturer/dashboard/current_semester`                 |
| **Security** | JWT Required (Role: L)                                |
| **Success Status** | `200 OK`                                              |
| **Error Status** | `404 Not Found` (No active semester), `403 Forbidden` |

#### Response Body
| Field | Type | Description |
| :--- | :--- | :--- |
| `semester_year` | `integer` | The academic year of the active semester. |
| `semester_number` | `integer` | The semester index (1, 2, or 3). |
| `status` | `string` | The current stage of the semester (e.g., `SUB`, `SET`, `PUB`). |
| `constraint_end_date` | `string (ISO Date)` | The final deadline for lecturers to submit their constraints. |

**Example Response:**
```json
{
    "semester_year": 2026,
    "semester_number": 1,
    "status": "SUB",
    "constraint_end_date": "2026-10-15"
}
```

---

## 6. Telegram Notification Linking Endpoints (src/routes/external/lecturer/notifications.py)

These endpoints support Telegram account linking for push notifications.

### 6.1. Start Telegram Link Flow

Creates or reuses a Telegram token and returns the deep link the user should open.

| Property | Details |
| :--- | :--- |
| **Method** | `POST` |
| **Endpoint** | `/lecturer/notifications/telegram-link/start` |
| **Security** | JWT Required (Role: L) |
| **Success Status** | `200 OK` |

#### Response Fields
| Field | Type | Description |
| :--- | :--- | :--- |
| `is_linked` | `boolean` | Whether this user is already linked to Telegram. |
| `link_in_progress` | `boolean` | Whether token is active and awaiting Telegram `/start`. |
| `telegram_link` | `string \| null` | Deep link to bot with token. |
| `link_expires_at` | `string \| null` | Token expiry timestamp (ISO-8601). |

### 6.2. Get Telegram Link Status

Returns current linking status without generating a new token.

| Property | Details |
| :--- | :--- |
| **Method** | `GET` |
| **Endpoint** | `/lecturer/notifications/telegram-link/status` |
| **Security** | JWT Required (Role: L) |
| **Success Status** | `200 OK` |

### 6.3. Backward-Compatible Telegram Link Endpoint

Legacy endpoint still used by older clients.

| Property | Details |
| :--- | :--- |
| **Method** | `GET` |
| **Endpoint** | `/lecturer/notifications/telegram-link` |
| **Security** | JWT Required (Role: L) |
| **Success Status** | `200 OK` |

### 5.2. Get My Assigned Courses
Retrieves a list of all courses the authenticated lecturer is assigned to, joined with specific course and offering details.

| Property | Details                                               |
| :--- |:------------------------------------------------------|
| **Method** | `GET`                                                 |
| **Endpoint** | `lecturer/dashboard/my_courses`                       |
| **Security** | JWT Required (Role: L)                                |
| **Success Status** | `200 OK` (Return a list of objects)                   |
| **Error Status** | `404 Not Found` (No active semester), `403 Forbidden` |

#### Course Object
| Field            | Type                 | Description |
|:-----------------|:---------------------| :--- |
| `course_number`  | `integer`            | The unique identifier for the course. |
| `course_name`    | `string`             | The title of the course. |
| `group_number`   | `integer`            | The specific section/group number for this offering. |
| `academic_year`  | `integer` | The academic year the course is offered. |
| `semester`     |   `integer` | The semester number. |
| `role` | `string`  | The lecturer's responsibility for this course. |

### Example Response:
```
JSON
[
    {
        "course_number": 20417,
        "course_name": "Algorithms",
        "group_number": 1,
        "academic_year": 2026,
        "semester": 1,
        "role": "Lecturer"
    }
]
```
