# Data Loader Pipeline

Bulk-load lecturer and course data from Excel files directly into the
database via the repository layer.

## Overview

This module ingests data from Excel files into the Schedula database. It
parses Excel, transforms it into per-table payloads, deduplicates records,
and persists them through the repositories — there are **no** internal HTTP
calls.

The pipeline is split in two phases so semester-independent data (lecturers,
courses) can be loaded once and reused across many semesters:

1. **Static data** — `users` and `courses`. Loaded from a slim deduplicated
   lecturer file (no course/semester columns) and the courses file.
2. **Assignment data** — `course_offering`, `offering_cohorts`, and
   `lecturer_courses`. Loaded from the full lecturer file (with course /
   year / semester / group columns) and the courses file (for cohorts).

The target semester referenced by the assignment file must already exist in
the `semesters` table; otherwise `load_assignments` returns
`{"status": "failure"}` and the wrapping route returns `400`.

### Data flow

```
Excel files (lecturer_dedu.xlsx, lecturer_full.xlsx, courses.xlsx)
        │
        ▼
excel_reader.py  →  pandas DataFrames
        │
        ▼
mapper.py        →  per-table payloads:
                      • users               (deduplicated)
                      • courses             (deduplicated)
                      • course_offerings    (one per row, deduplicated)
                      • offering_cohorts    (from Cohort_year column)
                      • lecturer_courses    (one per lecturer-row)
        │
        ▼
api_client.py    →  repository writes (idempotent on re-run)
        │
        ▼
PostgreSQL
```

## Components

### `config.py`
Excel column mappings and the lecturer role constant.

**Lecturers full file (`LECTURERS_COLUMNS`)** — used by `map_lecturers`:
- `USER_ID`, `ID_NUMBER` → user identity (`ID_NUMBER` preferred when present)
- `FIRST_NAME`, `LAST_NAME`, `EMAIL`, `DEPARTMENT`
- `COURSE`, `DEGREE_LEVEL`, `GROUP_NUMBER`, `YEAR`, `SEMESTER` — assignment data

**Lecturers dedu file (`LECTURERS_DEDU_COLUMNS`)** — used by `map_users_from_dedu`:
- Identity columns only: `USER_ID`, `ID_NUMBER`, `FIRST_NAME`, `LAST_NAME`,
  `EMAIL`, `DEPARTMENT`. (No course/year/semester columns.)

**Courses file (`COURSES_COLUMNS`)** — used by `map_courses`:
- `DEPARTMENT`, `DEGREE_LEVEL`, `COURSE` → course identity
- `NAME`, `CREDIT_POINTS`
- `Cohort_year` (optional) → emits an `offering_cohorts` row

### `excel_reader.py`
`read_lecturers_excel(file_bytes)` and `read_courses_excel(file_bytes)` are
thin wrappers around `pd.read_excel(...).dropna(how="all")`.

### `mapper.py`
- `map_users_from_dedu(df)` → `[user, ...]`. Deduplicates on the chosen id.
  Zero-pads `user_id` to 9 digits to satisfy
  `users.user_id CHECK (LENGTH = 9)`.
- `map_lecturers(df)` → `(users, offerings, lecturer_courses)`. Same id
  selection rules as `map_users_from_dedu`. Offerings are deduplicated on
  `(course_number, academic_year, semester, group_number)`.
- `map_courses(df)` → `(courses, cohorts)`. Cohorts are emitted only when
  `Cohort_year` is present; deduplicated on
  `(course_number, target_department_id, target_year_level)`.
- `group_cohorts_by_course(cohorts)` → `{course_number: [cohort, ...]}` for
  attaching cohorts to their offerings.

### `api_client.py`
`DataLoaderClient` — repository-backed loader (the name is historical; no
HTTP). Provides:

- `create_users(users)` → `{user_id: user_internal_id}`. Lookups by
  `user_name` then `email` before insert; treats DB unique-violations
  (`pgcode 23xxx`) as "skip and keep going".
- `create_courses(courses)` → number of newly inserted courses, with the
  same skip-on-duplicate behavior.
- `create_offerings(offerings)` → `{(course_number, year, semester, group):
  offering_id}`. Each offering may carry a `cohorts` key; cohorts are
  inserted atomically with the offering by the repository.
- `create_lecturer_courses(lc, user_map, offering_map)` → number of links
  inserted; resolves logical keys to FKs via the maps from the previous
  steps. Unresolvable rows are logged and skipped.
- `resolve_users_from_db(uids)` → `{user_id: user_internal_id}` for
  `load_assignments`, which doesn't re-insert users.

### `converter.py`
- `load_static_data(lecturers_dedu_bytes, courses_bytes)` → users + courses.
- `load_assignments(lecturers_bytes, courses_bytes)` → offerings (with
  cohorts) + lecturer-course links. Validates that the referenced semester
  exists in `semesters` and returns `{"status": "failure"}` otherwise.
- `convert_and_load(lecturers_dedu_bytes, lecturers_bytes, courses_bytes)`
  — convenience wrapper that runs both phases. Used by `run_wet.py`.

### `test_converter.py`
`test_and_export_excel(lecturers_bytes, courses_bytes, output_path)` runs
the full mapping pipeline without touching the DB and exports the resulting
five tables to a single Excel workbook with simulated auto-increment PKs:
`users`, `courses`, `course_offering`, `offering_cohorts`,
`lecturer_courses`.

### `run_wet.py`
Standalone wet-run script. Opens its own DB pool, runs `convert_and_load`,
then disconnects.

## API endpoints

These live in `src/routes/external/secretary/setup.py` (and a mirror in
`src/routes/dev_routes/setUp.py`).

### `POST /secretary/setup/load_data`

Loads static data (users + courses).

Multipart form fields:
- `lecturers_dedu_file` (XLSX) — slim deduplicated lecturer file
- `courses_file` (XLSX)

Response:
```json
{
  "status": "success",
  "users_loaded": 279,
  "courses_loaded": 243
}
```

### `POST /secretary/setup/load_assignments`

Loads offerings (with cohorts) and lecturer-course links. The semester
referenced by the file must already exist in the `semesters` table.

Multipart form fields:
- `lecturers_file` (XLSX) — full lecturer file
- `courses_file` (XLSX)

Response:
```json
{
  "status": "success",
  "offerings_loaded": 281,
  "lecturer_courses_loaded": 709
}
```

Returns `400` with `{"detail": "Semester YYYY/N not found in DB. Please create it first."}`
if the semester is missing.

### `POST /secretary/setup/load_data_test`

Same input as `/load_assignments` but writes the mapped tables to
`/tmp/test_output.xlsx` instead of the DB. Useful for verifying mapping logic.

## Usage

### Programmatic
```python
from src.input_convertor.converter import load_static_data, load_assignments

await load_static_data(lecturers_dedu_bytes, courses_bytes)
await load_assignments(lecturers_full_bytes, courses_bytes)
```

### Wet run from the CLI
```bash
python -m src.input_convertor.run_wet \
    --lecturers-dedu src/input_convertor/lecturer_full.xlsx \
    --lecturers      src/input_convertor/lecturer_full.xlsx \
    --courses        src/input_convertor/courses_full.xlsx
```

`lecturer_full.xlsx` works as the dedu input as well — the dedu mapper
ignores course/semester columns. Maintain a separately filtered file only
if you want a strict separation.

### Via curl
```bash
curl -X POST http://localhost:8000/secretary/setup/load_data \
  -F "lecturers_dedu_file=@lecturer_dedu.xlsx" \
  -F "courses_file=@courses_full.xlsx"

curl -X POST http://localhost:8000/secretary/setup/load_assignments \
  -F "lecturers_file=@lecturer_full.xlsx" \
  -F "courses_file=@courses_full.xlsx"

curl -X POST http://localhost:8000/secretary/setup/load_data_test \
  -F "lecturers_file=@lecturer_full.xlsx" \
  -F "courses_file=@courses_full.xlsx"
```

## Idempotency

All four `create_*` methods check for existing rows before inserting and
treat any `23xxx` (constraint violation) `pgcode` as "skip this row". This
makes re-runs safe for the common case (re-uploading the same files).

Errors that are *not* constraint violations are logged with full traceback
and re-raised, so a misconfigured DB or schema mismatch fails loudly.

## File layout

```
src/input_convertor/
├── config.py            # Column mappings + LECTURER_ROLE
├── excel_reader.py      # Read XLSX → DataFrame
├── mapper.py            # DataFrame → per-table payloads
├── api_client.py        # Repository-backed loader (DataLoaderClient)
├── converter.py         # load_static_data / load_assignments / convert_and_load
├── test_converter.py    # Dry-run pipeline → Excel export
├── run_wet.py           # Standalone wet-run CLI
├── lecturer.xlsx        # Sample lecturer data
├── lecturer_full.xlsx   # Sample lecturer data (full columns)
├── courses.xlsx         # Sample courses data
├── courses_full.xlsx    # Sample courses data
└── README.md
```

## Requirements

- `pandas`
- `openpyxl`
- `asyncpg` (via the repository layer)
- `fastapi` (for the wrapping endpoints)

## Notes

- `role` for users emitted by these mappers is hardcoded to `"L"` (lecturer).
  Secretaries are not created here.
- `user_name` is set to the same value as `user_id` (a 9-digit zero-padded
  string).
- `phone_num` and other notification settings are *not* set by this pipeline;
  they live in `user_notifications` and are managed via the
  `/dev/user-notifications/` routes after a user exists.
- Database tables must exist before loading: hit `POST /db/init` (when dev
  routes are enabled) or run the SQL in `src/database/init_db.sql`.
