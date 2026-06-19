# Schedula Solver Service

The solver service is a critical microservice in the Schedula architecture that solves course scheduling problems using constraint satisfaction programming (CSP). It uses **Google OR-Tools CP-SAT solver** to generate feasible course schedules while respecting system constraints and user-defined preferences. The CP-SAT model is feasibility-only (no objective function); soft constraints are encoded as assumptions and conflicting ones are surfaced via minimal unsatisfiable cores.

## Overview

The solver service operates as an event-driven consumer that:
- Listens for constraint update events via RabbitMQ
- Batches multiple updates for the same semester to optimize performance
- Fetches course offerings and lecturer constraints from PostgreSQL
- Solves the scheduling problem using CP-SAT with conflict detection
- Saves solutions back to the database and publishes results

## Architecture

### Technology Stack
- **Python 3.12+** - Runtime environment
- **Google OR-Tools** - CP-SAT constraint solver engine
- **RabbitMQ (aio_pika)** - Asynchronous message queue for event-driven communication
- **PostgreSQL (asyncpg)** - Database for offerings, constraints, and schedules

### Key Components

#### 1. Service Layer (`src/main.py`)
- **`SolverService`**: Event-driven service using RabbitMQ consumer pattern
- **Batching Optimization**: Intelligently batches constraint updates
  - Processes same-semester updates together (e.g., multiple lecturers updating constraints)
  - Configurable batch timeout (1.5s) and max batch size (100 messages)
  - Max wait time (3s) from first message to prevent starvation
- **Message Handling**: Processes constraint update events and triggers solving
- **Lifecycle Management**: Manages RabbitMQ connection and database pool

#### 2. Solver Engine (`src/solver.py`)
- **`CSPSolver`**: Core constraint satisfaction solver using OR-Tools CP-SAT
- **Scheduling Window**:
  - Sunday-Thursday: 08:00-20:00 (12-hour slots)
  - Friday: 08:00-15:00 (7-hour slots, respecting religious/cultural needs)
  - 1-hour granularity for course scheduling
- **Day Indexing**: 1-indexed (1=Sunday, 2=Monday, ..., 6=Friday) matching DB convention

#### 3. Database Layer (`src/db.py`)
- **`Database`**: Connection pool manager using asyncpg
- **Raw SQL Queries**: No ORM for performance and control
- Fetches offerings with lecturers and target cohorts
- Retrieves lecturer constraints with structured rules
- Manages draft schedules and solution persistence

## Constraint Model

### Hard Constraints (System-Enforced)

1. **One Day Assignment**: Each offering must be scheduled on exactly one day
2. **No Lecturer Cloning**: A lecturer cannot teach multiple courses at the same time
3. **No Student Conflicts**: Courses targeting the same cohort (department + year level) cannot overlap
4. **Duration Fit**: Courses must fit within the day's scheduling window based on credit points. The duration is computed by `_calculate_course_hours` (`src/solver.py`):
   - `CP <= 1` -> 1 hour
   - `CP <= 2` -> 2 hours
   - `CP <= 4.5` -> 3 hours (covers 3, 3.5, 4, 4.5 CP)
   - `CP <= 5` -> 4 hours (logically two 2-hour lectures, currently encoded as a single 4-hour block)
   - `CP > 5` -> `math.ceil(credit_points)` (fallback)

### Soft / Hard Atomic Constraints (User-Defined)

Lecturer-defined rules live in the `lecturer_constraints` row alongside an optional `secretary_override_as_hard` flag. The solver expects `structured_rules` to be a JSON object with an `atomic_constraints` array; only entries with `type: "block"` are currently honored. Each atomic carries its own `priority` (`hard` or `soft`, defaulting to `soft`).

```json
{
  "secretary_override_as_hard": null,
  "structured_rules": {
    "atomic_constraints": [
      {
        "type": "block",
        "priority": "soft",
        "days": [1, 3],
        "time_slot": {"start_hour": 8, "end_hour": 20}
      },
      {
        "type": "block",
        "priority": "hard",
        "days": [2],
        "time_slot": {"start_hour": 9, "end_hour": 12}
      }
    ]
  }
}
```

Resolution rules (see `src/solver.py`):

- **`secretary_override_as_hard`** is the top-level escape hatch:
  - `true` -> all atomics for this constraint are forced hard.
  - `false` -> all atomics are forced soft.
  - `null` (default) -> per-atomic `priority` is used.
- **Hard atomics** are added directly to the model and cause `failed` if violated.
- **Soft atomics** are added as CP-SAT assumptions and may be relaxed; violated assumptions surface in `broken_constraints`.
- Atomics without a recognized `type` are skipped with a log warning.

**Conflict Detection**: When infeasible, the solver returns a list of `(constraints_id, atomic_index)` pairs that form a minimal unsatisfiable core. The core enumeration loop is bounded by `MUS_MAX_ITERATIONS` and `MUS_MAX_WALL_TIME` (see Configuration).

### Prioritization Strategy

Uses **cohort-based prioritization** via CP-SAT decision strategy:
- Offerings targeting more cohorts are harder to schedule
- Solver processes multi-cohort courses first (CHOOSE_FIRST strategy)
- Reduces search space and improves solve times

## Message Flow

### Input (RabbitMQ)
**Queue**: `constraints_request_queue`

Only `semester_year` and `semester_number` are required for solving.
Producers may include additional metadata fields (`new_constraint_id`, `lecturer_id`, `run_id`, `trigger_type`) for traceability and an optional `schedule_id` to target an existing draft schedule row instead of creating one.

```json
{
  "new_constraint_id": 42,
  "lecturer_id": 101,
  "semester_year": 2024,
  "semester_number": 1,
  "schedule_id": 5
}
```

### Output (RabbitMQ)
**Queue**: `constraints_response_queue`

**Success Case**:
```json
{
  "schedule_id": 5,
  "semester_year": 2024,
  "semester_number": 1,
  "status": "solved",
  "solution_count": 24
}
```

**Failure Case**:
```json
{
  "schedule_id": 5,
  "semester_year": 2024,
  "semester_number": 1,
  "status": "failed",
  "broken_constraints": [
    {"constraints_id": 42, "atomic_index": 0},
    {"constraints_id": 57, "atomic_index": 1},
    {"constraints_id": 91, "atomic_index": 0}
  ]
}
```

## Database Schema

### Input Tables
- **`course_offering`**: Offerings with semester and group numbers
- **`courses`**: Joined to read `credit_points` for each offering
- **`lecturer_courses`**: Lecturer assignments to offerings
- **`offering_cohorts`**: Target departments and year levels (both NOT NULL)
- **`lecturer_constraints`**: User-defined constraints with `structured_rules` JSONB and `secretary_override_as_hard`

### Output Tables
- **`schedules`**: Draft/approved schedules per semester
- **`courses_schedules`**: Scheduled sessions (offering, lecturer, day, start/end time)
- **`breaking_constraints`**: Persisted record of MUS-detected conflicts. Maintained by `clean_stale_breaking_constraints`, `save_breaking_constraints`, and `remove_resolved_constraints` in `src/db.py`.

## Performance Characteristics

- **Solver Timeout**: 60 seconds per semester (`max_time_in_seconds = 60.0`)
- **Batch Processing**: Reduces redundant solves for simultaneous constraint updates. The consumer uses `prefetch_count=1` and acks only after the batch is processed, so most "batching" deduplicates same-semester messages observed during a single iteration rather than gathering many concurrently delivered RabbitMQ messages.
- **Decision Strategy**: Prioritizes multi-cohort offerings for faster convergence
- **Connection Pooling**: Efficient PostgreSQL connection reuse
- **MUS Loop**: Bounded enumeration of conflicting soft assumptions (see `MUS_MAX_ITERATIONS` and `MUS_MAX_WALL_TIME` below).

## Testing

Comprehensive test suite in `tests/`:

```bash
# Run all tests
pytest tests/

# Specific test categories
pytest tests/unit/                         # Unit tests
pytest tests/integration/                  # Integration tests
pytest tests/load/                         # Load/performance tests
pytest -m "not load"                       # Skip slow load tests
```

Test infrastructure includes:
- Mock constraint factories for reproducible test data
- Database integration tests with real PostgreSQL
- Pipeline reliability tests for edge cases
- Semester isolation verification

## Development

### Local Setup

```bash
# Install dependencies
uv pip install -e ".[test]"

# Set environment variables
export DATABASE_URL="postgresql://user:pass@localhost:5432/schedula"
export RABBITMQ_URL="amqp://rabbitmq:rabbitmq@localhost:5672/"

# Run service
python -m src.main
```

### Docker Deployment

```bash
# Build image
docker build -t schedula-solver .

# Run with docker-compose (from SchedulaDeployment root)
docker compose up solver
```

## Configuration

Environment variables:
- **`DATABASE_URL`**: PostgreSQL connection string (required)
- **`RABBITMQ_URL`**: RabbitMQ AMQP URL (default: `amqp://rabbitmq:rabbitmq@rabbitmq:5672/`)
- **`MUS_MAX_ITERATIONS`** (default `100`): cap on MUS enumeration iterations per failed solve.
- **`MUS_MAX_WALL_TIME`** (default `300.0` seconds): wall-clock cap on the MUS enumeration loop. Whatever conflicts have been collected when the cap is hit are returned in `broken_constraints`.

Both MUS variables are wired in `SchedulaDeployment/docker-compose.yml` under the `solver` service.

Batching tuning (in `src/main.py`):
- **`BATCH_TIMEOUT_SECONDS`**: 1.5s - Wait time after last message
- **`MAX_BATCH_SIZE`**: 100 - Process immediately when reached
- **`MAX_BATCH_WAIT_SECONDS`**: 3.0s - Absolute max wait from first message

## Conflict Resolution

When solver returns `status: "failed"`:
1. The CP-SAT solver computes a **minimal unsatisfiable core** of soft assumptions via `SufficientAssumptionsForInfeasibility()`.
2. The solver iterates: it disables the offending assumptions and re-solves, accumulating additional cores until the model becomes satisfiable, the MUS loop hits `MUS_MAX_ITERATIONS`, or it exceeds `MUS_MAX_WALL_TIME`.
3. Each entry returned in `broken_constraints` is a `{constraints_id, atomic_index}` pair pointing at a single atomic inside `structured_rules.atomic_constraints`.
4. Hard infeasibility detected before the assumption loop (for example, a course that cannot fit in any day) is reported as `status: "failed"` with `broken_constraints: []`.
5. Backend can:
   - Persist the conflicts in `breaking_constraints`.
   - Notify affected lecturers (handled by the backend, not the solver).
   - Suggest constraint relaxation or mark the schedule as requiring manual intervention.

**Note**: Each individual core is minimal and sufficient to prove infeasibility for that iteration. The accumulated list across iterations is broader than a single MUS but is bounded by the configured caps.