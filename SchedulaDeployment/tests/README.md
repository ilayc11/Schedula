# E2E Test Suite

End-to-end tests for the Schedula scheduling system. These tests exercise the full pipeline: **Backend API → RabbitMQ → Solver → Database**, verifying that the CSP solver produces correct schedules under different constraint scenarios.

## Prerequisites

All services must be running before executing tests:

```bash
docker-compose up --build
```

Required services: **Backend**, **PostgreSQL**, **RabbitMQ**, **Solver**.

## Running Tests

```bash
# Run all E2E tests (each test clears the DB, so order matters)
pytest tests/ -v -s

# Run a specific test
pytest tests/test_happy_path.py -v -s
pytest tests/test_realistic_university.py -v -s

# Generate data without running assertions (useful for debugging)
python tests/generate_test_data.py --scenario happy_path
python tests/generate_test_data.py --scenario realistic_university
```

## Test Scenarios

### 1. Happy Path (`test_happy_path.py`)

**Purpose:** Verify the solver works correctly with simple, easily satisfiable constraints.

| Property | Value |
|---|---|
| Lecturers | 50 |
| Courses | 50 (3 credit points each) |
| Constraints | 1 per lecturer — blocks one morning or afternoon on a random weekday |
| Expected result | **Solved** — all or nearly all courses scheduled (≥95%) |

**What it validates:**
- Solver produces a feasible schedule
- Course sessions are saved to the database
- Basic constraint enforcement works

---

### 2. Over-Constrained Path (`test_over_constrained_path.py`)

**Purpose:** Stress-test the solver with many overlapping constraints that are challenging but still satisfiable.

| Property | Value |
|---|---|
| Lecturers | 50 |
| Courses | 50 (3 credit points each) |
| Constraints | 1–6 blocks per lecturer, distributed by tier: 30% light (1–2), 50% medium (3–4), 20% heavy (5–6) |
| Expected result | **Solved** — ≥90% of courses scheduled |

**What it validates:**
- Solver handles complex constraint landscapes
- Performance under load (reports solve time, sessions/second)
- High constraint density doesn't cause false failures

---

### 3. Failure Path (`test_failure_path.py`)

**Purpose:** Verify the solver correctly detects and reports impossible constraints.

| Property | Value |
|---|---|
| Lecturers | 50 |
| Courses | 50 (3 credit points each) |
| Constraints | Every lecturer blocks **all 6 days** entirely (8:00–20:00 / 8:00–15:00 Friday) |
| Expected result | **Failed** — solver reports conflict, no schedule saved |

**What it validates:**
- Solver returns `status: "failed"` (not a crash or timeout)
- Breaking constraints are identified and saved to `breaking_constraints` table
- Breaking constraint records have correct structure (`breaking_id`, `constraints_id`, `atomic_constraint_index`, `lecturer_name`)
- No course sessions are persisted for a failed solve
- System handles failure gracefully

---

### 4. Partial Failure Path (`test_partial_failure_path.py`)

**Purpose:** Verify the solver correctly isolates which specific constraints are impossible when only some lecturers have unsatisfiable constraints.

| Property | Value |
|---|---|
| Good lecturers | 5 (block Monday morning only) |
| Bad lecturers | 2 (block all 6 days entirely) |
| Courses | 7 (one per lecturer, round-robin assignment) |
| Expected result | **Failed** — only the bad lecturers' constraints flagged as breaking |

**What it validates:**
- MUS (Minimal Unsatisfiable Subset) detection correctly identifies only the impossible constraints
- Good lecturers' constraints are **not** incorrectly flagged
- Bad lecturers' constraints **are** flagged
- Breaking constraints stored with correct structure and lecturer details

---

### 5. Realistic University (`test_realistic_university.py`)

**Purpose:** Test the solver against a plausible real-world university dataset with varied course loads, cross-department offerings, team-teaching, and diverse constraint types.

| Property | Value |
|---|---|
| Departments | 3 — CS (12 lecturers), Math (10), EE (8) |
| Lecturers | 30 total |
| Courses | 40 with varied credit points (2, 3, 4, or 5 hours) |
| Cross-listed courses | ~6 courses shared across departments (multi-cohort) |
| Team-teaching | ~15% of courses have 2 lecturers assigned |
| Lecturer load | 1–3 courses per lecturer |
| Constraint distribution | ~20% none, ~30% simple (1 block), ~25% medium (2–3 blocks), ~15% complex (3–4 blocks with hard priority), ~10% secretary override |
| Expected result | **Solved** — ≥95% of courses scheduled, no invariant violations |

**What it validates:**
- **Coverage** — nearly all courses are scheduled despite realistic pressure
- **Lecturer no-overlap** — no lecturer has overlapping sessions on the same day
- **Day/time bounds** — all sessions end by 20:00 (Sun–Thu) or 15:00 (Friday)
- **Duration validity** — scheduled durations are positive and match credit points
- **Cohort no-overlap** — cross-listed courses don't conflict (via cohort-based NoOverlap)
- **Hard/soft priority logic** — complex constraints with mixed priorities are handled
- **Secretary override** — overridden constraints are enforced correctly
- **Day distribution** — reports how sessions spread across the week (quality metric)
- **Multi-course lecturers** — reports lecturers with same-day courses (quality metric)

---

## Test Infrastructure

### Key Files

| File | Purpose |
|---|---|
| `conftest.py` | Pytest fixtures (URLs, semester config, RabbitMQ queue management) |
| `test_data_generators.py` | Shared functions for creating lecturers, courses, offerings, constraints |
| `generate_test_data.py` | CLI tool for generating data without running tests |

### Data Flow

1. **Clear database** — wipe all existing data via `DELETE /db/clear`
2. **Create semester** — set up test semester with SUB status
3. **Create lecturers** — generate lecturer users via dev API
4. **Create courses & offerings** — create courses with offerings and cohort assignments
5. **Assign lecturers** — link lecturers to offerings (round-robin or realistic distribution)
6. **Create constraints** — submit structured constraints via dev API (triggers RabbitMQ messages to solver)
7. **Wait for solver** — poll `GET /dev/solver-runs/semester/{year}/{semester}` until status is `solved` or `failed`
8. **Verify results** — check sessions, breaking constraints, and invariants via dev API

### Configuration

Defaults in `conftest.py`:

| Setting | Default | Environment Variable |
|---|---|---|
| Backend URL | `http://localhost:8000` | `BACKEND_URL` |
| RabbitMQ URL | `amqp://rabbitmq:rabbitmq@localhost:5672/` | `RABBITMQ_URL` |
| Test year | 2025 | — |
| Test semester | 1 | — |

### CLI Data Generator

```bash
python tests/generate_test_data.py --scenario <name> [options]

Scenarios:
  happy_path             Simple constraints, easily solvable
  over_constrained       Many overlapping constraints, challenging but solvable
  failure_path           All days blocked, impossible to solve
  realistic_university   Real-world university setup (fixed 30 lecturers, 40 courses)

Options:
  --backend-url URL      Backend API URL (default: http://localhost:8000)
  --year YEAR            Semester year (default: 2025)
  --semester {1,2,3}     Semester number (default: 1)
  --lecturers N          Number of lecturers (default: 50, ignored for realistic_university)
  --courses N            Number of courses (default: 50, ignored for realistic_university)
```
