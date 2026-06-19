-- Create Users Table
CREATE TABLE IF NOT EXISTS users (
    user_internal_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_name VARCHAR(255) NOT NULL UNIQUE,
    user_id VARCHAR(9) NOT NULL UNIQUE CHECK (LENGTH(user_id) = 9),
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    department_id INTEGER,

    role CHAR(1) NOT NULL CHECK (role IN ('L', 'S'))
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_user_name ON users(user_name);

-- USER NOTIFICATIONS
CREATE TABLE IF NOT EXISTS user_notifications (
    notification_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_internal_id BIGINT NOT NULL UNIQUE REFERENCES users(user_internal_id) ON DELETE CASCADE,
    phone_num VARCHAR(20) CHECK (phone_num IS NULL OR phone_num ~ '^\+[1-9][0-9]{1,14}$'),
    telegram_chat_id VARCHAR(50),
    telegram_token VARCHAR(100) UNIQUE,
    telegram_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    email_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_user_notif_telegram_token ON user_notifications(telegram_token);


-- COURSES
CREATE TABLE IF NOT EXISTS courses (
    course_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    department_id INTEGER NOT NULL,  -- Which department OWNS/DESIGNS this course
    degree_level SMALLINT NOT NULL,
    course_number INTEGER NOT NULL UNIQUE,
    course_name VARCHAR(255) NOT NULL,
    credit_points NUMERIC(4,2) NOT NULL,

    -- When FALSE, the solver skips this course entirely. Used to opt-out
    -- non-classroom rows like research/exemption/final-project entries that
    -- otherwise inflate cohort load and block feasible schedules.
    is_scheduleable BOOLEAN NOT NULL DEFAULT TRUE
);

-- Idempotent column addition for environments where the table already exists
-- without the is_scheduleable column (init_db.sql is rerunnable).
ALTER TABLE courses
    ADD COLUMN IF NOT EXISTS is_scheduleable BOOLEAN NOT NULL DEFAULT TRUE;

CREATE INDEX IF NOT EXISTS idx_courses_name ON courses(course_name);
CREATE INDEX IF NOT EXISTS idx_courses_course_number ON courses(course_number);
CREATE INDEX IF NOT EXISTS idx_courses_scheduleable ON courses(is_scheduleable);


-- COURSE OFFERING
CREATE TABLE IF NOT EXISTS course_offering (
    offering_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    course_number INTEGER NOT NULL,
    academic_year INT NOT NULL,
    semester SMALLINT NOT NULL,
    group_number INT NOT NULL,

    CONSTRAINT fk_course_offering_course
        FOREIGN KEY (course_number)
        REFERENCES courses(course_number)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT uq_course_offering UNIQUE (course_number, academic_year, semester, group_number)
);

CREATE INDEX IF NOT EXISTS idx_course_offering_course ON course_offering(course_number);


-- OFFERING COHORTS
-- Cohort tracking: Which students (department + year level) this offering is FOR
-- NOTE: Different from courses.department_id which indicates who OWNS the course
-- Example: A CS course (courses.department_id=1) can be offered to Math students (target_department_id=2)
-- IMPORTANT: Both target_department_id and target_year_level are REQUIRED (NOT NULL)
-- This ensures every cohort is precisely defined (no ambiguous NULL semantics)
CREATE TABLE IF NOT EXISTS offering_cohorts (
    cohort_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    offering_id BIGINT NOT NULL,
    target_department_id INTEGER NOT NULL,
    target_year_level SMALLINT NOT NULL CHECK (target_year_level >= 1 AND target_year_level <= 4),

    CONSTRAINT fk_offering_cohorts_offering
        FOREIGN KEY (offering_id)
        REFERENCES course_offering(offering_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT uq_offering_cohorts UNIQUE (offering_id, target_department_id, target_year_level)
);

CREATE INDEX IF NOT EXISTS idx_offering_cohorts_offering ON offering_cohorts(offering_id);
CREATE INDEX IF NOT EXISTS idx_offering_cohorts_cohort ON offering_cohorts(target_department_id, target_year_level);



-- LECTURER COURSES
CREATE TABLE IF NOT EXISTS lecturer_courses (
    lecturer_course_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    lecturer_internal_id BIGINT NOT NULL,
    offering_id BIGINT NOT NULL,
    role VARCHAR(50),

    CONSTRAINT fk_lecturer_courses_user
        FOREIGN KEY (lecturer_internal_id)
        REFERENCES users(user_internal_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT fk_lecturer_courses_offering
        FOREIGN KEY (offering_id)
        REFERENCES course_offering(offering_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT uq_lecturer_courses UNIQUE (lecturer_internal_id, offering_id)
);

CREATE INDEX IF NOT EXISTS idx_lecturer_courses_user ON lecturer_courses(lecturer_internal_id);
CREATE INDEX IF NOT EXISTS idx_lecturer_courses_offering ON lecturer_courses(offering_id);



-- SEMESTERS
CREATE TABLE IF NOT EXISTS semesters (
    semester_year INTEGER NOT NULL,
    semester_number INTEGER NOT NULL CHECK (semester_number BETWEEN 1 AND 3),
    semester_start_date DATE NOT NULL,
    semester_end_date DATE NOT NULL,
    constraint_start_date DATE NOT NULL,
    constraint_end_date DATE NOT NULL,
    change_period_start DATE NOT NULL,
    change_period_end DATE NOT NULL,
    status VARCHAR(3) NOT NULL CHECK (status IN ('SET','SUB','REV','CHA','PUB')),
    PRIMARY KEY (semester_year, semester_number),
    CHECK (semester_end_date >= semester_start_date),
    CHECK (constraint_end_date >= constraint_start_date),
    CHECK (change_period_end >= change_period_start)
);

CREATE INDEX IF NOT EXISTS idx_semesters_status ON semesters(status);
CREATE INDEX IF NOT EXISTS idx_semesters_dates ON semesters(semester_year, semester_number, semester_start_date, semester_end_date);


-- PERIOD NOTIFICATION EVENT IDEMPOTENCY
CREATE TABLE IF NOT EXISTS period_notification_events (
    event_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    semester_year INTEGER NOT NULL,
    semester_number INTEGER NOT NULL,
    event_key VARCHAR(100) NOT NULL,
    event_date DATE NOT NULL,
    payload JSONB NOT NULL,
    source VARCHAR(50) NOT NULL,
    published_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_period_event_semester
        FOREIGN KEY (semester_year, semester_number)
        REFERENCES semesters(semester_year, semester_number)
        ON DELETE CASCADE,

    CONSTRAINT uq_period_event UNIQUE (semester_year, semester_number, event_key, event_date)
);

CREATE INDEX IF NOT EXISTS idx_period_event_unpublished ON period_notification_events(published_at);
CREATE INDEX IF NOT EXISTS idx_period_event_semester ON period_notification_events(semester_year, semester_number);


-- LAST OBSERVED SEMESTER STATUS FOR CHANGE DETECTION
CREATE TABLE IF NOT EXISTS semester_period_state (
    semester_year INTEGER NOT NULL,
    semester_number INTEGER NOT NULL,
    last_seen_status VARCHAR(3) NOT NULL CHECK (last_seen_status IN ('SET','SUB','REV','CHA','PUB')),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (semester_year, semester_number),

    CONSTRAINT fk_period_state_semester
        FOREIGN KEY (semester_year, semester_number)
        REFERENCES semesters(semester_year, semester_number)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_period_state_status ON semester_period_state(last_seen_status);



-- SCHEDULES
CREATE TABLE IF NOT EXISTS schedules (
    schedule_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    semester_year INTEGER NOT NULL,
    semester_number INTEGER NOT NULL,
    is_draft BOOLEAN NOT NULL DEFAULT TRUE,
    is_published BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_update TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP WITH TIME ZONE,
    
    CONSTRAINT fk_schedules_semester FOREIGN KEY (semester_year, semester_number)
        REFERENCES semesters(semester_year, semester_number)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
    
    CONSTRAINT schedules_last_update_after_created_chk CHECK (last_update >= created_at),
    CONSTRAINT schedules_published_after_created_chk CHECK (published_at IS NULL OR published_at >= created_at)
);

CREATE INDEX IF NOT EXISTS idx_schedules_semester ON schedules(semester_year, semester_number);
CREATE INDEX IF NOT EXISTS idx_schedules_published ON schedules(is_published, published_at);



-- LECTURER_CONSTRAINTS
CREATE TABLE IF NOT EXISTS lecturer_constraints (
    constraints_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    lecturer_internal_id BIGINT NOT NULL,
    schedule_id BIGINT,
    semester_year INTEGER NOT NULL,
    semester_number INTEGER NOT NULL,
    raw_text TEXT,
    structured_rules JSONB,
    secretary_override_as_hard BOOLEAN,  -- NULL = use per-atomic priority, TRUE/FALSE = override all atomics
    is_manually_edited BOOLEAN NOT NULL DEFAULT FALSE,  -- TRUE when secretary edited the structured rules
    original_raw_text TEXT,  -- Lecturer's original raw_text before secretary edit; NULL if never edited
    last_updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_constraints_user FOREIGN KEY (lecturer_internal_id)
        REFERENCES users(user_internal_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT fk_constraints_semester FOREIGN KEY (semester_year, semester_number)
        REFERENCES semesters(semester_year, semester_number)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT fk_constraints_schedule FOREIGN KEY (schedule_id)
        REFERENCES schedules(schedule_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_constraints_user ON lecturer_constraints(lecturer_internal_id);
CREATE INDEX IF NOT EXISTS idx_constraints_semester ON lecturer_constraints(semester_year, semester_number);
CREATE INDEX IF NOT EXISTS idx_constraints_user_semester ON lecturer_constraints(lecturer_internal_id, semester_year, semester_number);
CREATE INDEX IF NOT EXISTS idx_constraints_updated ON lecturer_constraints(last_updated_at);
CREATE INDEX IF NOT EXISTS idx_constraints_structured_gin ON lecturer_constraints USING GIN (structured_rules);
CREATE INDEX IF NOT EXISTS idx_constraints_manually_edited ON lecturer_constraints(is_manually_edited);



-- BREAKING_CONSTRAINTS
-- Stores grouped breaking atomic constraints by parent constraint_id
CREATE TABLE IF NOT EXISTS breaking_constraints (
    breaking_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    constraints_id BIGINT NOT NULL,
    breaking_atomic_constraints JSONB NOT NULL,  -- Array of {atomic_constraint_index, days, type, time_slot}
    semester_year INTEGER NOT NULL,
    semester_number INTEGER NOT NULL,
    is_seen BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_breaking_constraint
        FOREIGN KEY (constraints_id)
        REFERENCES lecturer_constraints(constraints_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_breaking_semester
        FOREIGN KEY (semester_year, semester_number)
        REFERENCES semesters(semester_year, semester_number)
        ON DELETE CASCADE,

    CONSTRAINT uq_breaking_constraint_semester UNIQUE (constraints_id, semester_year, semester_number)
);

CREATE INDEX IF NOT EXISTS idx_breaking_semester ON breaking_constraints(semester_year, semester_number);
CREATE INDEX IF NOT EXISTS idx_breaking_seen ON breaking_constraints(is_seen);
CREATE INDEX IF NOT EXISTS idx_breaking_atomic_gin ON breaking_constraints USING GIN (breaking_atomic_constraints);



-- COURSES_SCHEDULES
CREATE TABLE IF NOT EXISTS courses_schedules (
    session_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    offering_id BIGINT NOT NULL,
    lecturer_internal_id BIGINT NOT NULL,
    schedule_id BIGINT NOT NULL,

    day_of_week SMALLINT NOT NULL CHECK (day_of_week BETWEEN 1 AND 6),
    start_time TIME NOT NULL,
    end_time TIME NOT NULL CHECK (end_time > start_time),

    CONSTRAINT fk_session_offering FOREIGN KEY (offering_id)
        REFERENCES course_offering(offering_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT fk_session_lecturer FOREIGN KEY (lecturer_internal_id)
        REFERENCES users(user_internal_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT fk_session_schedule FOREIGN KEY (schedule_id)
        REFERENCES schedules(schedule_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT uq_session UNIQUE (offering_id, schedule_id, lecturer_internal_id, day_of_week, start_time),
    CONSTRAINT chk_session_time_ranges CHECK (
        (day_of_week BETWEEN 1 AND 5 AND end_time <= TIME '20:00')
        OR (day_of_week = 6 AND end_time <= TIME '14:00')
    )
);

CREATE INDEX IF NOT EXISTS idx_session_offering ON courses_schedules(offering_id);
CREATE INDEX IF NOT EXISTS idx_session_lecturer ON courses_schedules(lecturer_internal_id);
CREATE INDEX IF NOT EXISTS idx_session_schedule ON courses_schedules(schedule_id);
CREATE INDEX IF NOT EXISTS idx_session_schedule_lecturer ON courses_schedules(schedule_id, lecturer_internal_id);
CREATE INDEX IF NOT EXISTS idx_session_day_time ON courses_schedules(day_of_week, start_time);



-- SCHEDULE APPROVALS
CREATE TABLE IF NOT EXISTS schedule_approvals (
    scheapprov_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    schedule_id BIGINT NOT NULL,
    lecturer_internal_id BIGINT NOT NULL,
    status VARCHAR(3) NOT NULL CHECK (status IN ('PEN','APP','REJ')),

    CONSTRAINT fk_sa_schedule FOREIGN KEY (schedule_id)
        REFERENCES schedules(schedule_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT fk_sa_user FOREIGN KEY (lecturer_internal_id)
        REFERENCES users(user_internal_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT uq_schedule_lecturer UNIQUE (schedule_id, lecturer_internal_id)
);

CREATE INDEX IF NOT EXISTS idx_sa_user ON schedule_approvals(lecturer_internal_id);
CREATE INDEX IF NOT EXISTS idx_sa_status ON schedule_approvals(status);


-- FAIRNESS REPORTS
CREATE TABLE IF NOT EXISTS fairness_reports (
    report_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    schedule_id BIGINT NOT NULL,
    lecturer_internal_id BIGINT NOT NULL,
    score DOUBLE PRECISION NOT NULL CHECK (score >= 0),
    fullfilled_constraints_json JSONB,
    broken_constraints_json JSONB,

    CONSTRAINT fk_fr_schedule FOREIGN KEY (schedule_id)
        REFERENCES schedules(schedule_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT fk_fr_user FOREIGN KEY (lecturer_internal_id)
        REFERENCES users(user_internal_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT uq_fairness_schedule_lecturer UNIQUE (schedule_id, lecturer_internal_id)
);

CREATE INDEX IF NOT EXISTS idx_fr_schedule ON fairness_reports(schedule_id);
CREATE INDEX IF NOT EXISTS idx_fr_user ON fairness_reports(lecturer_internal_id);
CREATE INDEX IF NOT EXISTS idx_fr_score ON fairness_reports(score);
CREATE INDEX IF NOT EXISTS idx_fr_fullfilled_gin ON fairness_reports USING GIN (fullfilled_constraints_json);
CREATE INDEX IF NOT EXISTS idx_fr_broken_gin ON fairness_reports USING GIN (broken_constraints_json);



-- SOLVER RUNS
-- Tracks CSP solver execution results for each semester
CREATE TABLE IF NOT EXISTS solver_runs (
    run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    semester_year INTEGER NOT NULL,
    semester_number INTEGER NOT NULL,
    schedule_id BIGINT,
    status VARCHAR(10) NOT NULL CHECK (status IN ('pending', 'solved', 'failed')),
    broken_constraints JSONB,
    -- Distinguishes 'user_constraints' (relaxable lecturer constraints conflict),
    -- 'base_model' (system hard constraints alone are unsat), and
    -- 'data_infeasible' (course/lecturer load exceeds weekly capacity).
    -- NULL when status != 'failed'.
    failure_reason VARCHAR(32) CHECK (failure_reason IS NULL OR failure_reason IN ('user_constraints', 'base_model', 'data_infeasible')),
    -- Structured payload for data_infeasible failures: the offending cohorts,
    -- lecturers, and the per-week capacity used during the check. Empty/NULL
    -- for other failure modes.
    failure_details JSONB,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,

    CONSTRAINT fk_solver_runs_semester FOREIGN KEY (semester_year, semester_number)
        REFERENCES semesters(semester_year, semester_number)
        ON DELETE CASCADE
        ON UPDATE CASCADE,

    CONSTRAINT fk_solver_runs_schedule FOREIGN KEY (schedule_id)
        REFERENCES schedules(schedule_id)
        ON DELETE SET NULL
        ON UPDATE CASCADE
);

-- Idempotent column additions for environments where the table already exists
-- without the new fields (init_db.sql is rerunnable).
ALTER TABLE solver_runs
    ADD COLUMN IF NOT EXISTS failure_reason VARCHAR(32),
    ADD COLUMN IF NOT EXISTS failure_details JSONB;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'solver_runs_failure_reason_check'
    ) THEN
        ALTER TABLE solver_runs
            ADD CONSTRAINT solver_runs_failure_reason_check
            CHECK (failure_reason IS NULL OR failure_reason IN ('user_constraints', 'base_model', 'data_infeasible'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_solver_runs_semester ON solver_runs(semester_year, semester_number);
CREATE INDEX IF NOT EXISTS idx_solver_runs_status ON solver_runs(status);
CREATE INDEX IF NOT EXISTS idx_solver_runs_created ON solver_runs(created_at DESC);

