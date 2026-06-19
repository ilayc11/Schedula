import os
import asyncpg
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.pool = None
        self.url = os.getenv("DATABASE_URL")

    async def connect(self):
        if not self.url:
            raise ValueError("DATABASE_URL environment variable is not set")
        try:
            self.pool = await asyncpg.create_pool(self.url)
            logger.info("Connected to Database")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    async def close(self):
        if self.pool:
            await self.pool.close()
            logger.info("Database connection closed")

    async def get_semester_data(self, year: int, number: int) -> Dict[str, Any]:
        if not self.pool:
            raise RuntimeError("Database not connected")

        # 1. Fetch Offerings with Lecturers, Course Details, and Cohorts
        # We aggregate lecturers and cohorts because one offering might have multiple of each.
        # course_number is needed by the solver so that parallel groups of the
        # same course are treated as alternatives from the cohort's perspective.
        # Non-scheduleable courses (research, exemptions, final projects, etc.)
        # are filtered out so they don't consume slots or inflate cohort load.
        # COALESCE preserves backward compatibility with older DBs that don't
        # yet have the is_scheduleable column populated for every row.
        offerings_query = """
            SELECT 
                co.offering_id,
                co.course_number,
                c.credit_points,
                co.group_number,
                array_agg(DISTINCT lc.lecturer_internal_id) FILTER (WHERE lc.lecturer_internal_id IS NOT NULL) as lecturers,
                array_agg(
                    DISTINCT jsonb_build_object(
                        'target_department_id', oc.target_department_id,
                        'target_year_level', oc.target_year_level
                    )
                ) FILTER (WHERE oc.cohort_id IS NOT NULL) as cohorts
            FROM course_offering co
            JOIN courses c ON co.course_number = c.course_number
            LEFT JOIN lecturer_courses lc ON co.offering_id = lc.offering_id
            LEFT JOIN offering_cohorts oc ON co.offering_id = oc.offering_id
            WHERE co.academic_year = $1 AND co.semester = $2
              AND COALESCE(c.is_scheduleable, TRUE) = TRUE
            GROUP BY co.offering_id, co.course_number, c.credit_points, co.group_number
        """

        # 2. Fetch Constraints
        constraints_query = """
            SELECT 
                constraints_id,
                lecturer_internal_id, 
                structured_rules,
                secretary_override_as_hard
            FROM lecturer_constraints
            WHERE semester_year = $1 AND semester_number = $2
        """

        async with self.pool.acquire() as conn:
            # Fetch Offerings
            offering_rows = await conn.fetch(offerings_query, year, number)
            offerings = []
            for row in offering_rows:
                # Handle case where lecturers array might be empty
                lecturers = row['lecturers'] if row['lecturers'] else []
                
                # Parse cohorts from jsonb array
                cohorts = []
                if row['cohorts']:
                    for cohort_json in row['cohorts']:
                        # Handle case where asyncpg returns JSONB as string
                        if isinstance(cohort_json, str):
                            import json
                            cohort_json = json.loads(cohort_json)
                        
                        cohorts.append({
                            "target_department_id": cohort_json.get('target_department_id'),
                            "target_year_level": cohort_json.get('target_year_level')
                        })
                
                offerings.append({
                    "offering_id": row['offering_id'],
                    "course_number": row['course_number'],
                    "credit_points": float(row['credit_points']),
                    "group_number": row['group_number'],
                    "lecturers": lecturers,
                    "cohorts": cohorts
                })

            # Fetch Constraints
            constraint_rows = await conn.fetch(constraints_query, year, number)
            constraints = []
            for row in constraint_rows:
                constraint = dict(row)
                # Parse structured_rules if it's a JSON string
                # asyncpg usually auto-deserializes JSONB, but handle string case for safety
                if isinstance(constraint.get('structured_rules'), str):
                    import json
                    try:
                        constraint['structured_rules'] = json.loads(constraint['structured_rules'])
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning(f"Failed to parse structured_rules for constraint {constraint.get('constraints_id')}: {e}")
                        constraint['structured_rules'] = {}
                constraints.append(constraint)

        return {
            "offerings": offerings,
            "constraints": constraints
        }

    async def get_all_constraints_by_semester(self, year: int, number: int) -> List[Dict[str, Any]]:
        if not self.pool:
            raise RuntimeError("Database not connected")
        
        query = """
            SELECT 
                constraints_id, 
                lecturer_internal_id, 
                structured_rules, 
                priority
            FROM lecturer_constraints
            WHERE semester_year = $1 AND semester_number = $2
        """
        # Note: 'priority' column exists in atomic_constraint but let's check init_db.sql
        # init_db.sql shows: lecturer_constraints(..., structured_rules JSONB, ...)
        # It doesn't show a separate 'priority' column, it might be inside structured_rules or I need to check schema again.
        # Looking at init_db.sql:
        # CREATE TABLE IF NOT EXISTS lecturer_constraints (
        #     constraints_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        #     ...
        #     structured_rules JSONB,
        #     ...
        # );
        # So I should just fetch structured_rules.
        
        query = """
            SELECT 
                constraints_id, 
                lecturer_internal_id, 
                structured_rules
            FROM lecturer_constraints
            WHERE semester_year = $1 AND semester_number = $2
        """
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, year, number)
            constraints = []
            for row in rows:
                constraint = dict(row)
                # Parse structured_rules if it's a JSON string
                if isinstance(constraint.get('structured_rules'), str):
                    import json
                    try:
                        constraint['structured_rules'] = json.loads(constraint['structured_rules'])
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.warning(f"Failed to parse structured_rules for constraint {constraint.get('constraints_id')}: {e}")
                        constraint['structured_rules'] = {}
                constraints.append(constraint)
            return constraints

    async def get_or_create_draft_schedule(
        self,
        year: int,
        number: int,
        requested_schedule_id: Optional[int] = None,
    ) -> int:
        """Resolve which draft schedule to write the next solution to.

        Resolution order:
        1. If ``requested_schedule_id`` is provided AND that schedule exists for
           the given semester AND is still a draft, use it. This honors the
           ``schedule_id`` the API caller advertised in the queue message so
           the row that was returned to the user is the one that ends up with
           sessions.
        2. Otherwise, return the most recent draft for the semester
           (``ORDER BY schedule_id DESC``) - matches what the backend's
           ``get_latest_schedule_for_semester`` returns.
        3. Otherwise, INSERT a new draft as a last resort (e.g., the very
           first solver run of the semester or after every draft has been
           published).
        """
        if not self.pool:
            raise RuntimeError("Database not connected")

        # 1. Honor the requested schedule_id when valid.
        requested_query = """
            SELECT schedule_id FROM schedules
            WHERE schedule_id = $1
              AND semester_year = $2
              AND semester_number = $3
              AND is_draft = TRUE
        """

        # 2. Fall back to the newest draft for the semester.
        find_query = """
            SELECT schedule_id FROM schedules
            WHERE semester_year = $1 AND semester_number = $2 AND is_draft = TRUE
            ORDER BY schedule_id DESC
            LIMIT 1
        """

        # 3. Final fallback: create a new draft.
        create_query = """
            INSERT INTO schedules (semester_year, semester_number, is_draft)
            VALUES ($1, $2, TRUE)
            RETURNING schedule_id
        """

        async with self.pool.acquire() as conn:
            if requested_schedule_id is not None:
                row = await conn.fetchrow(
                    requested_query, requested_schedule_id, year, number
                )
                if row:
                    logger.info(
                        f"Using requested draft schedule_id={row['schedule_id']} "
                        f"for semester {year}/{number}"
                    )
                    return row['schedule_id']
                logger.warning(
                    f"Requested schedule_id={requested_schedule_id} for semester "
                    f"{year}/{number} is not a valid draft; falling back to newest draft"
                )

            row = await conn.fetchrow(find_query, year, number)
            if row:
                logger.info(
                    f"Using newest draft schedule_id={row['schedule_id']} "
                    f"for semester {year}/{number}"
                )
                return row['schedule_id']

            row = await conn.fetchrow(create_query, year, number)
            logger.info(
                f"Created new draft schedule_id={row['schedule_id']} "
                f"for semester {year}/{number}"
            )
            return row['schedule_id']

    async def save_solution(self, schedule_id: int, sessions: List[Dict[str, Any]]):
        """
        Replaces all sessions for the given schedule_id with the new list.
        """
        if not self.pool:
            raise RuntimeError("Database not connected")
            
        delete_query = "DELETE FROM courses_schedules WHERE schedule_id = $1"
        
        insert_query = """
            INSERT INTO courses_schedules 
            (offering_id, lecturer_internal_id, schedule_id, day_of_week, start_time, end_time)
            VALUES ($1, $2, $3, $4, $5, $6)
        """
        
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # 1. Clear old schedule
                await conn.execute(delete_query, schedule_id)
                
                # 2. Insert new sessions
                if sessions:
                    data = [
                        (
                            s['offering_id'], 
                            s['lecturer_id'], 
                            schedule_id, 
                            s['day_of_week'], 
                            s['start_time'], 
                            s['end_time']
                        ) 
                        for s in sessions
                    ]
                    await conn.executemany(insert_query, data)
                
                # 3. Update last_update timestamp on schedule
                await conn.execute("UPDATE schedules SET last_update = CURRENT_TIMESTAMP WHERE schedule_id = $1", schedule_id)

    async def clear_breaking_constraints(self, year: int, number: int) -> int:
        """
        Clear all breaking constraints for a specific semester.
        Returns the number of rows deleted.
        """
        if not self.pool:
            raise RuntimeError("Database not connected")
        
        delete_query = """
            DELETE FROM breaking_constraints 
            WHERE semester_year = $1 AND semester_number = $2
        """
        
        async with self.pool.acquire() as conn:
            result = await conn.execute(delete_query, year, number)
            # Result format is "DELETE N" where N is the number of deleted rows
            if result and result.startswith("DELETE"):
                count = int(result.split()[-1])
                logger.info(f"Cleared {count} breaking constraints for semester {year}/{number}")
                return count
            return 0

    async def clean_stale_breaking_constraints(self, year: int, number: int) -> int:
        """
        Remove breaking constraints that reference invalid atomic constraint indices.
        This handles the case where a user edited their constraint text.
        (Deleted constraints are auto-removed via ON DELETE CASCADE)
        
        With the grouped structure, checks if any atomic_constraint_index in the
        breaking_atomic_constraints array is out of range.
        
        Args:
            year: Semester year
            number: Semester number
        
        Returns:
            Number of stale constraints removed
        """
        if not self.pool:
            raise RuntimeError("Database not connected")
        
        # Fetch all breaking constraints with their associated structured_rules
        query = """
            SELECT 
                bc.breaking_id,
                bc.constraints_id,
                bc.breaking_atomic_constraints,
                lc.structured_rules
            FROM breaking_constraints bc
            JOIN lecturer_constraints lc ON bc.constraints_id = lc.constraints_id
            WHERE bc.semester_year = $1 AND bc.semester_number = $2
        """
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, year, number)
            
            stale_ids = []
            for row in rows:
                structured_rules = row['structured_rules']
                breaking_atomics = row['breaking_atomic_constraints']
                
                # Parse JSON if needed
                if isinstance(structured_rules, str):
                    import json
                    try:
                        structured_rules = json.loads(structured_rules)
                    except (json.JSONDecodeError, TypeError):
                        stale_ids.append(row['breaking_id'])
                        continue
                
                if isinstance(breaking_atomics, str):
                    import json
                    try:
                        breaking_atomics = json.loads(breaking_atomics)
                    except (json.JSONDecodeError, TypeError):
                        stale_ids.append(row['breaking_id'])
                        continue
                
                # Check if all atomic_constraint_indices are valid
                if isinstance(structured_rules, dict) and isinstance(breaking_atomics, list):
                    atomic_constraints = structured_rules.get('atomic_constraints', [])
                    if not isinstance(atomic_constraints, list):
                        stale_ids.append(row['breaking_id'])
                        continue
                    
                    # Check each breaking atomic constraint's index
                    for breaking_atomic in breaking_atomics:
                        if isinstance(breaking_atomic, dict):
                            atomic_idx = breaking_atomic.get('atomic_constraint_index')
                            if atomic_idx is None or atomic_idx >= len(atomic_constraints):
                                stale_ids.append(row['breaking_id'])
                                break  # This group is stale
                else:
                    # Malformed data, mark as stale
                    stale_ids.append(row['breaking_id'])
            
            # Delete stale entries
            if stale_ids:
                delete_query = """
                    DELETE FROM breaking_constraints 
                    WHERE breaking_id = ANY($1::bigint[])
                """
                result = await conn.execute(delete_query, stale_ids)
                if result and result.startswith("DELETE"):
                    count = int(result.split()[-1])
                    logger.info(f"Cleaned {count} stale breaking constraint groups for semester {year}/{number}")
                    return count
            
            return 0

    async def remove_resolved_constraints(self, year: int, number: int, constraint_ids: List[int]) -> int:
        """
        Remove breaking constraints for constraints that are no longer breaking.
        Called when the solver succeeds with constraints that were previously breaking.
        
        Args:
            year: Semester year
            number: Semester number
            constraint_ids: List of constraint IDs that were successfully scheduled
        
        Returns:
            Number of breaking constraints removed
        """
        if not self.pool:
            raise RuntimeError("Database not connected")
        
        if not constraint_ids:
            return 0
        
        delete_query = """
            DELETE FROM breaking_constraints
            WHERE semester_year = $1 
              AND semester_number = $2 
              AND constraints_id = ANY($3::bigint[])
        """
        
        async with self.pool.acquire() as conn:
            result = await conn.execute(delete_query, year, number, constraint_ids)
            if result and result.startswith("DELETE"):
                count = int(result.split()[-1])
                logger.info(f"Removed {count} resolved breaking constraints for semester {year}/{number}")
                return count
            return 0

    async def save_breaking_constraints(self, year: int, number: int, constraints: List[Dict[str, Any]]) -> int:
        """
        Save breaking constraints to the database (grouped by constraints_id).
        
        Args:
            year: Semester year
            number: Semester number
            constraints: List of dicts with keys: constraints_id, atomic_index
        
        Returns:
            Number of constraint groups saved
        """
        if not self.pool:
            raise RuntimeError("Database not connected")
        
        if not constraints:
            logger.info("No breaking constraints to save")
            return 0
        
        # Group breaking constraints by constraints_id
        grouped = {}
        for constraint in constraints:
            c_id = constraint['constraints_id']
            atomic_idx = constraint['atomic_index']
            
            if c_id not in grouped:
                grouped[c_id] = []
            grouped[c_id].append(atomic_idx)
        
        logger.info(f"Grouped {len(constraints)} breaking atomic constraints into {len(grouped)} constraint groups")
        logger.info(f"Breaking constraint IDs: {sorted(grouped.keys())}")
        
        # Fetch structured_rules for all affected constraints to get atomic constraint details
        fetch_query = """
            SELECT constraints_id, structured_rules, lecturer_internal_id
            FROM lecturer_constraints
            WHERE constraints_id = ANY($1::bigint[])
        """
        
        insert_query = """
            INSERT INTO breaking_constraints 
            (constraints_id, breaking_atomic_constraints, semester_year, semester_number)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (constraints_id, semester_year, semester_number)
            DO UPDATE SET 
                breaking_atomic_constraints = EXCLUDED.breaking_atomic_constraints,
                created_at = CURRENT_TIMESTAMP,
                is_seen = FALSE
        """
        
        async with self.pool.acquire() as conn:
            # Fetch all constraint details
            constraint_ids = list(grouped.keys())
            constraint_rows = await conn.fetch(fetch_query, constraint_ids)
            constraint_details = {row['constraints_id']: row for row in constraint_rows}
            
            count = 0
            for c_id, atomic_indices in grouped.items():
                if c_id not in constraint_details:
                    logger.warning(f"Constraint {c_id} not found in database, skipping")
                    continue
                
                details = constraint_details[c_id]
                structured_rules = details['structured_rules']
                
                # Handle JSON parsing if needed
                if isinstance(structured_rules, str):
                    import json
                    try:
                        structured_rules = json.loads(structured_rules)
                    except (json.JSONDecodeError, TypeError):
                        logger.warning(f"Failed to parse structured_rules for constraint {c_id}")
                        continue
                
                atomic_constraints = structured_rules.get('atomic_constraints', [])
                
                # Build array of breaking atomic constraints with their indices
                breaking_atomics = []
                for atomic_idx in atomic_indices:
                    if 0 <= atomic_idx < len(atomic_constraints):
                        atomic = atomic_constraints[atomic_idx]
                        breaking_atomics.append({
                            "atomic_constraint_index": atomic_idx,
                            "days": atomic.get('days', []),
                            "type": atomic.get('type', 'block'),
                            "time_slot": atomic.get('time_slot')
                        })
                    else:
                        logger.warning(f"Atomic index {atomic_idx} out of range for constraint {c_id}")
                
                if not breaking_atomics:
                    logger.warning(f"No valid breaking atomic constraints for constraint {c_id}")
                    continue
                
                try:
                    import json
                    result = await conn.execute(
                        insert_query,
                        c_id,
                        json.dumps(breaking_atomics),
                        year,
                        number
                    )
                    if result:
                        count += 1
                        logger.debug(f"Saved breaking constraint group for constraint {c_id} with {len(breaking_atomics)} atomic constraint(s)")
                except Exception as e:
                    logger.error(f"Error inserting breaking constraint group {c_id}: {e}")
            
            logger.info(f"Saved {count} breaking constraint groups for semester {year}/{number}")
            return count

db = Database()

