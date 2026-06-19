import json
import logging
import math
import os
import time as time_module
from typing import List, Dict, Any, Union, Tuple
from datetime import time
from ortools.sat.python import cp_model

logger = logging.getLogger(__name__)

class CSPSolver:
    def __init__(self):
        # Configuration
        self.start_hour = 8
        # Day limits (exclusive end of scheduling window in terms of completion)
        # Slots are 0-indexed starting at 8:00.
        # Days are 1-indexed: 1=Sunday, 2=Monday, 3=Tuesday, 4=Wednesday, 5=Thursday, 6=Friday
        # This matches both DB convention and LLM pipeline output.
        # Limits:
        # Sun-Thu (1-5): 08:00 - 20:00.
        # Fri (6): 08:00 - 15:00.
        
        self.end_hour_regular = 20
        self.end_hour_friday = 15
        
        # Days to schedule: 1 to 6
        self.days = list(range(1, 7)) 

    def _calculate_course_hours(self, credit_points: float) -> int:
            """
            Calculates the actual lecture hours based on credit points.
            Rules:
            1 CP = 1 hour
            2 CP = 2 hours
            3 CP = 3 hours
            3.5 CP = 3 hours
            4 CP = 3 hours
            4.5 CP = 3 hours
            5 CP = 4 hours (2 lectures of 2 hours each - currently returned as total)
            """
            if credit_points <= 1:
                return 1
            elif credit_points <= 2:
                return 2
            elif credit_points <= 4.5:
                return 3
            elif credit_points <= 5:
                return 4  # Represents 2x2, but for now returned as total duration
            else:
                return math.ceil(credit_points) # Fallback for unexpected values
            
    def _time_to_slot(self, time_str: str) -> int:
        """Converts HH:MM string to hour index from start_hour."""
        try:
            parts = time_str.split(':')
            h = int(parts[0])
            # Assuming 1-hour granularity as per plan
            return h - self.start_hour
        except:
            return 0

    def _slot_to_time(self, slot: int) -> time:
        """Converts slot index to time object."""
        h = self.start_hour + slot
        return time(hour=h, minute=0)

    def _weekly_capacity_hours(self) -> int:
        """Total schedulable hours in one week (matches the day windows above)."""
        sun_thu = (self.end_hour_regular - self.start_hour) * 5  # 5 days * 12h
        friday = self.end_hour_friday - self.start_hour          # 7h
        return sun_thu + friday

    def _check_data_feasibility(
        self,
        offerings: List[Dict[str, Any]],
        durations: Dict[Any, int],
    ) -> Dict[str, Any]:
        """Cheap upfront feasibility check on the offerings dataset.

        Detects two structural problems that would make the CP-SAT model
        unsatisfiable regardless of any user constraints:

        1. Per-cohort over-subscription: total course hours that *must* fit
           into a cohort's weekly window exceeds available capacity. Each
           course is counted once per cohort (groups are alternatives, see
           the cohort no-overlap loop below).
        2. Per-lecturer over-subscription: total course hours assigned to a
           single lecturer exceeds their weekly capacity (groups taught by
           the same lecturer cannot overlap, so they sum).

        Returns ``{"infeasible": False}`` if everything fits, otherwise a
        descriptive dict that the caller can surface to the API.
        """
        weekly_cap = self._weekly_capacity_hours()

        # Per-cohort hours: course-deduplicated (same course's groups count once)
        cohort_course_hours: Dict[Tuple[int, int], Dict[Any, int]] = {}
        for o in offerings:
            course_key = o.get('course_number', o['offering_id'])
            h = durations.get(o['offering_id'], 0)
            for cohort in o.get('cohorts', []):
                dept = cohort.get('target_department_id')
                year = cohort.get('target_year_level')
                if dept is None or year is None:
                    continue
                ck = (dept, year)
                cohort_course_hours.setdefault(ck, {})[course_key] = h

        infeasible_cohorts = []
        for ck, by_course in cohort_course_hours.items():
            total = sum(by_course.values())
            if total > weekly_cap:
                infeasible_cohorts.append({
                    "cohort": {"target_department_id": ck[0], "target_year_level": ck[1]},
                    "required_hours": total,
                    "available_hours": weekly_cap,
                    "course_count": len(by_course),
                })

        # Per-lecturer hours (every offering counted, no dedup — groups must serialize)
        lecturer_hours: Dict[int, int] = {}
        for o in offerings:
            h = durations.get(o['offering_id'], 0)
            for lect_id in o.get('lecturers', []) or []:
                lecturer_hours[lect_id] = lecturer_hours.get(lect_id, 0) + h

        infeasible_lecturers = [
            {"lecturer_internal_id": lid, "required_hours": hrs, "available_hours": weekly_cap}
            for lid, hrs in lecturer_hours.items()
            if hrs > weekly_cap
        ]

        if not infeasible_cohorts and not infeasible_lecturers:
            return {"infeasible": False}

        # Sort worst offenders first for readable logs / API output.
        infeasible_cohorts.sort(key=lambda x: -x["required_hours"])
        infeasible_lecturers.sort(key=lambda x: -x["required_hours"])

        return {
            "infeasible": True,
            "weekly_capacity_hours": weekly_cap,
            "infeasible_cohorts": infeasible_cohorts,
            "infeasible_lecturers": infeasible_lecturers,
        }

    def solve(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Solves the scheduling problem.
        
        Args:
            data: Dict containing:
                - offerings: List of offering dicts
                - constraints: List of lecturer constraint dicts
        
        Returns:
            Dict with keys:
                - status: "solved" or "failed"
                - solution: List of session dicts (if solved)
                - conflict_constraints: List of constraint IDs (if failed)
                - used_constraint_ids: List of constraint IDs used in solution (if solved)
                - failure_reason: One of "user_constraints" | "base_model" |
                  "data_infeasible" when status == "failed"; absent on success.
                - infeasible_cohorts / infeasible_lecturers: only present when
                  failure_reason == "data_infeasible".
        """
        offerings = data.get('offerings', [])
        constraints_data = data.get('constraints', [])
        
        logger.info(f"Solving for {len(offerings)} offerings with constraints from {len(constraints_data)} lecturers.")
        
        # Count constraints with secretary override for logging
        override_count = sum(1 for c in constraints_data if c.get('secretary_override_as_hard') is not None)
        logger.info(f"Constraints: {len(constraints_data)} total, {override_count} with secretary override")

        model = cp_model.CpModel()
        
        # --- Variables ---
        # active[(offering_id, day)] -> BoolVar
        # start[(offering_id, day)] -> IntVar
        
        active = {} 
        starts = {}
        intervals = {}
        
        # Map offering details for easy access
        offering_map = {o['offering_id']: o for o in offerings}
        
        # Pre-calculate durations 
        durations = {}
        for o in offerings:
            durations[o['offering_id']] = self._calculate_course_hours(o['credit_points'])

        # --- Pre-flight feasibility check (cheap, before building CP model) ---
        feasibility = self._check_data_feasibility(offerings, durations)
        if feasibility.get("infeasible"):
            cohorts_over = feasibility["infeasible_cohorts"]
            lects_over = feasibility["infeasible_lecturers"]
            logger.warning(
                f"Pre-flight infeasibility: {len(cohorts_over)} cohort(s) and "
                f"{len(lects_over)} lecturer(s) exceed the {feasibility['weekly_capacity_hours']}h "
                f"weekly capacity"
            )
            for c in cohorts_over[:5]:
                logger.warning(
                    f"  cohort {c['cohort']}: {c['required_hours']}h required > "
                    f"{c['available_hours']}h available ({c['course_count']} courses)"
                )
            for l in lects_over[:5]:
                logger.warning(
                    f"  lecturer {l['lecturer_internal_id']}: {l['required_hours']}h required > "
                    f"{l['available_hours']}h available"
                )
            return {
                "status": "failed",
                "failure_reason": "data_infeasible",
                "solution": [],
                "conflict_constraints": [],
                "used_constraint_ids": [],
                "weekly_capacity_hours": feasibility["weekly_capacity_hours"],
                "infeasible_cohorts": cohorts_over,
                "infeasible_lecturers": lects_over,
            }


        # Sort offerings by number of target cohorts (descending)
        # Offerings targeting more departments/cohorts are harder to schedule
        # so we prioritize them by processing them first
        def get_cohort_count(offering):
            return len(offering.get('cohorts', []))
        
        sorted_offerings = sorted(offerings, key=get_cohort_count, reverse=True)
        logger.info(f"Prioritization: Offerings sorted by cohort count (max={get_cohort_count(sorted_offerings[0]) if sorted_offerings else 0}, min={get_cohort_count(sorted_offerings[-1]) if sorted_offerings else 0})")

        # Create variables for each offering (in priority order)
        for o in sorted_offerings:
            oid = o['offering_id']
            duration = durations[oid]
            
            day_actives = []
            
            for d in self.days:
                # Determine max slots for this day
                # Days 1-5 (Sun-Thu): 8-20
                # Day 6 (Fri): 8-15
                if d == 6:
                    max_hour = self.end_hour_friday
                else:
                    max_hour = self.end_hour_regular
                
                max_slots = max_hour - self.start_hour
                
                # If duration fits?
                if duration > max_slots:
                    # Cannot schedule on this day
                    continue

                suffix = f'_{oid}_d{d}'
                
                is_active = model.NewBoolVar(f'active{suffix}')
                day_actives.append(is_active)
                active[(oid, d)] = is_active
                
                # Start time variable
                # Must be between 0 and (max_slots - duration)
                # This ensures course finishes by max_hour
                start_var = model.NewIntVar(0, max_slots - duration, f'start{suffix}')
                starts[(oid, d)] = start_var
                
                # Interval variable (enforced only if active)
                # end_var is just derived for the interval
                end_var = model.NewIntVar(0, max_slots, f'end{suffix}')
                
                # Optional Interval: only active if is_active is true
                interval_var = model.NewOptionalIntervalVar(
                    start_var, 
                    duration, 
                    end_var, 
                    is_active, 
                    f'interval{suffix}'
                )
                intervals[(oid, d)] = interval_var
            
            # Constraint 1: Exactly one day selected
            if not day_actives:
                 logger.error(f"Offering {oid} (duration {duration}) cannot fit in any day!")
                 return {
                     "status": "failed",
                     "failure_reason": "data_infeasible",
                     "solution": [],
                     "conflict_constraints": [],
                     "used_constraint_ids": [],
                     "error": f"Offering {oid} (duration {duration}h) exceeds all day capacities"
                 }
            
            model.Add(sum(day_actives) == 1)

        # --- Lecturer Constraints ---
        
        # 1. No Overlap (Cloning) - Hard Constraint (System)
        lecturer_offerings = {} 
        for o in offerings:
            for lect_id in o['lecturers']:
                if lect_id not in lecturer_offerings:
                    lecturer_offerings[lect_id] = []
                lecturer_offerings[lect_id].append(o['offering_id'])
        
        for lect_id, oids in lecturer_offerings.items():
            for d in self.days:
                lect_intervals = []
                for oid in oids:
                    if (oid, d) in intervals:
                        lect_intervals.append(intervals[(oid, d)])
                
                if len(lect_intervals) > 1:
                    model.AddNoOverlap(lect_intervals)

        # 2. No Student Conflicts (Same Cohort) - Hard Constraint (System)
        # Group offerings by cohort (department + year level), bucketed by
        # course_number so that parallel groups of the same course are treated
        # as ALTERNATIVES from the cohort's perspective, not as separate
        # mandatory sessions. A student attends ONE group of a course, so the
        # cohort only needs one representative interval per course.
        #
        # If course_number is missing on the offering payload (older callers /
        # tests), fall back to using offering_id as the bucket key — this
        # preserves the legacy "every offering is a distinct course" behavior.
        # NOTE: Both dept_id and year_level are now REQUIRED (NOT NULL in DB).
        cohort_to_course_offerings: Dict[Tuple[int, int], Dict[Any, List[int]]] = {}
        for o in offerings:
            cohorts = o.get('cohorts', [])
            course_key = o.get('course_number', o['offering_id'])

            for cohort in cohorts:
                dept_id = cohort.get('target_department_id')
                year_level = cohort.get('target_year_level')

                if dept_id is None or year_level is None:
                    logger.warning(f"Skipping cohort with missing fields: dept={dept_id}, year={year_level}")
                    continue

                cohort_key = (dept_id, year_level)
                cohort_to_course_offerings.setdefault(cohort_key, {}) \
                                          .setdefault(course_key, []) \
                                          .append(o['offering_id'])

        # For each cohort and each day, add at most one interval per course
        # to the no-overlap set. The lecturer no-overlap loop above already
        # serializes groups taught by the same lecturer, so picking a single
        # representative per course is safe from the lecturer's perspective.
        for cohort_key, by_course in cohort_to_course_offerings.items():
            for d in self.days:
                cohort_intervals = []
                for oids in by_course.values():
                    day_ivs = [intervals[(oid, d)] for oid in oids if (oid, d) in intervals]
                    if day_ivs:
                        cohort_intervals.append(day_ivs[0])

                if len(cohort_intervals) > 1:
                    model.AddNoOverlap(cohort_intervals)

        # 3. User Defined Blocks (With Priority Branching)
        # Priority logic:
        # 1. Secretary override (secretary_override_as_hard) is highest authority
        # 2. If override=True, ALL atomics are hard (no assumptions)
        # 3. If override=False, ALL atomics are soft (with assumptions)
        # 4. If override=NULL, check per-atomic priority (default: 'soft')
        # 5. Hard atomics: added directly to model (must be satisfied)
        # 6. Soft atomics: added as assumptions (can be relaxed, appear in MUS)
        
        assumptions = []
        assumption_to_constraint = {}  # Maps assumption var to (constraint_id, atomic_index)

        logger.info(f"Processing {len(constraints_data)} constraint set(s) from database")
        
        for c_data in constraints_data:
            lect_id = c_data['lecturer_internal_id']
            c_id = c_data.get('constraints_id') 
            if c_id is None:
                logger.warning(f"Skipping constraint with no constraints_id for lecturer {lect_id}")
                continue

            # Secretary override: takes precedence over per-atomic priority (None = use atomic priority)
            secretary_override = c_data.get('secretary_override_as_hard')  # Can be True, False, or None
            
            structured = c_data.get('structured_rules', {})
            logger.debug(f"Processing constraint {c_id} for lecturer {lect_id} - secretary_override={secretary_override}")
            
            # Access atomic_constraints from the dict
            rules = structured.get('atomic_constraints', []) if isinstance(structured, dict) else []
            if not isinstance(structured, dict):
                logger.warning(f"Constraint {c_id} has structured_rules as {type(structured)} instead of dict - skipping")
                continue
            if not rules or not isinstance(rules, list):
                logger.warning(f"Constraint {c_id} has no atomic_constraints or invalid format - skipping")
                continue
            
            logger.debug(f"Constraint {c_id} has {len(rules)} atomic constraint(s)")
            
            oids = lecturer_offerings.get(lect_id, [])
            if not oids:
                logger.warning(f"Constraint {c_id} for lecturer {lect_id} has no offerings - cannot be enforced")
                continue
            
            # Process each atomic constraint with priority logic
            for atomic_idx, rule in enumerate(rules):
                # Determine if this atomic constraint is hard or soft
                if secretary_override is not None:
                    # Secretary override present - use it for all atomics
                    is_atomic_hard = secretary_override
                    priority_source = f"secretary_override={secretary_override}"
                else:
                    # No override - check per-atomic priority (default to 'soft' for missing)
                    atomic_priority = rule.get('priority', 'soft')
                    is_atomic_hard = (atomic_priority == 'hard')
                    priority_source = f"atomic_priority={atomic_priority}"
                
                logger.debug(f"  Atomic {atomic_idx}: {'HARD' if is_atomic_hard else 'SOFT'} (source: {priority_source})")
                
                # Process block constraints
                if rule.get('type') == 'block':
                    blocked_days = rule.get('days', []) 
                    time_slot = rule.get('time_slot') 
                    
                    if blocked_days is None: 
                        continue

                    # Create assumption variable ONCE per atomic (outside the day loop)
                    # so all days in this atomic are enforced/relaxed together
                    soft_assumption_var = None
                    if not is_atomic_hard:
                        soft_assumption_var = model.NewBoolVar(f'assumption_c{c_id}_a{atomic_idx}_d{"_".join(str(d) for d in blocked_days)}')
                        assumptions.append(soft_assumption_var)
                        assumption_to_constraint[soft_assumption_var] = (c_id, atomic_idx)

                    for atomic_day in blocked_days:
                        # LLM now outputs 1-indexed days matching DB convention directly
                        db_day = atomic_day
                        
                        if db_day not in self.days:
                            continue
                        
                        # Check if block covers whole day by examining time_slot values
                        # Full-day blocks: no time_slot, or 8:00-20:00 (regular) / 8:00-15:00 (Friday)
                        is_full_day = False
                        if not time_slot:
                            # No time_slot on a block means block the entire day
                            is_full_day = True
                        else:
                            start_hour = time_slot.get('start_hour')
                            end_hour = time_slot.get('end_hour')
                            # Check if it's a full-day block
                            if start_hour == 8:
                                if db_day == 6 and end_hour == 15:  # Friday
                                    is_full_day = True
                                elif db_day != 6 and end_hour == 20:  # Other days
                                    is_full_day = True
                        
                        if is_atomic_hard:
                            # HARD CONSTRAINT: Block without assumption (must be satisfied)
                            hard_constraint_added = False
                            if is_full_day:
                                # Block entire day
                                for oid in oids:
                                    if (oid, db_day) in active:
                                        model.Add(active[(oid, db_day)] == 0)
                                        hard_constraint_added = True
                            elif time_slot:
                                # Block specific time slot
                                start_hour = time_slot.get('start_hour')
                                end_hour = time_slot.get('end_hour')
                                
                                if start_hour is not None and end_hour is not None:
                                    # Convert hours to slot indices (relative to self.start_hour)
                                    block_start = start_hour - self.start_hour
                                    block_end = end_hour - self.start_hour
                                    
                                    for oid in oids:
                                        if (oid, db_day) not in starts:
                                            continue
                                        
                                        start_var = starts[(oid, db_day)]
                                        act_var = active[(oid, db_day)]
                                        duration = durations[oid]
                                        
                                        # Calculate forbidden start positions
                                        f_start = max(0, block_start - duration + 1)
                                        f_end = block_end - 1
                                        
                                        # HARD: Constraint enforced directly without assumption
                                        for forbidden_val in range(f_start, f_end + 1):
                                            if forbidden_val >= 0:
                                                model.Add(start_var != forbidden_val).OnlyEnforceIf(act_var)
                                        hard_constraint_added = True
                            
                            if hard_constraint_added:
                                logger.debug(f"→ Added as HARD constraint (cannot be relaxed)")
                        
                        else:
                            # SOFT CONSTRAINT: Block with assumption (can be relaxed)
                            # Reuse the single assumption_var created outside the day loop
                            
                            if is_full_day:
                                # Block entire day (soft - with assumption)
                                for oid in oids:
                                    if (oid, db_day) in active:
                                        model.Add(active[(oid, db_day)] == 0).OnlyEnforceIf(soft_assumption_var)
                            elif time_slot:
                                # Block specific time slot (soft - with assumption)
                                start_hour = time_slot.get('start_hour')
                                end_hour = time_slot.get('end_hour')
                                
                                if start_hour is not None and end_hour is not None:
                                    # Convert hours to slot indices
                                    block_start = start_hour - self.start_hour
                                    block_end = end_hour - self.start_hour
                                    
                                    for oid in oids:
                                        if (oid, db_day) not in starts:
                                            continue
                                        
                                        start_var = starts[(oid, db_day)]
                                        act_var = active[(oid, db_day)]
                                        duration = durations[oid]
                                        
                                        # Calculate forbidden start positions
                                        f_start = max(0, block_start - duration + 1)
                                        f_end = block_end - 1
                                        
                                        # SOFT: Constraint enforced by assumption AND active status
                                        for forbidden_val in range(f_start, f_end + 1):
                                            if forbidden_val >= 0:
                                                model.Add(start_var != forbidden_val).OnlyEnforceIf([act_var, soft_assumption_var])
                            
                            logger.debug(f"→ Added as SOFT constraint (can be relaxed if needed)")

        # --- Add Decision Strategy for Prioritization ---
        # Guide the solver to assign values to multi-cohort offerings first
        # Collect all active variables in priority order (sorted by cohort count)
        priority_active_vars = []
        for o in sorted_offerings:
            oid = o['offering_id']
            for d in self.days:
                if (oid, d) in active:
                    priority_active_vars.append(active[(oid, d)])
        
        # Add decision strategy: process variables in priority order
        if priority_active_vars:
            model.AddDecisionStrategy(
                priority_active_vars,
                cp_model.CHOOSE_FIRST,  # Follow the order we provided
                cp_model.SELECT_MAX_VALUE  # Try to assign True (1) first (schedule it)
            )
            logger.info(f"Decision strategy applied to {len(priority_active_vars)} priority variables")

        # --- Solve with All MUS Cores Detection ---
        logger.info(f"Adding {len(assumptions)} assumption variables to model")
        
        # Iteratively find all MUS cores
        all_conflict_constraints = []
        remaining_assumptions = assumptions.copy()
        excluded_assumptions = []  # Assumptions we've identified as conflicting
        
        # Configurable limits to find all breaking constraints
        max_iterations = int(os.environ.get('MUS_MAX_ITERATIONS', '100'))
        max_mus_wall_time = float(os.environ.get('MUS_MAX_WALL_TIME', '300.0'))
        mus_start_time = time_module.time()
        iteration = 0
        status = None  # Initialize status
        
        # Handle edge case: no assumptions means solve without assumptions
        if not remaining_assumptions:
            logger.info("No assumptions to check - solving base model")
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = 60.0
            status = solver.Solve(model)
        
        while remaining_assumptions and iteration < max_iterations:
            # Check wall-clock timeout
            elapsed = time_module.time() - mus_start_time
            if elapsed > max_mus_wall_time:
                logger.warning(
                    f"MUS detection wall-clock timeout after {iteration} iterations "
                    f"({elapsed:.1f}s). Found {len(all_conflict_constraints)} breaking constraints so far."
                )
                break
            iteration += 1
            logger.info(f"MUS detection iteration {iteration}: {len(remaining_assumptions)} assumptions remaining")
            
            # Create a FRESH solver for each iteration to avoid accumulating assumptions
            solver = cp_model.CpSolver()
            solver.parameters.max_time_in_seconds = 60.0
            
            # Try solving with remaining assumptions
            model.ClearAssumptions()  # Clear any previous assumptions
            model.AddAssumptions(remaining_assumptions)
            status = solver.Solve(model)
            
            if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                # Found a feasible solution with remaining constraints
                logger.info(f"Found feasible solution in iteration {iteration}")
                break
            elif status == cp_model.INFEASIBLE:
                # Get the minimal unsatisfiable core
                conflict_var_indices = solver.SufficientAssumptionsForInfeasibility()
                
                if not conflict_var_indices:
                    logger.warning("No conflict core returned, breaking")
                    break
                
                # Map variable indices to (constraint_id, atomic_index) pairs
                core_constraints = []
                for var_idx in conflict_var_indices:
                    actual_var_idx = abs(var_idx)
                    for assumption_var in remaining_assumptions:
                        if assumption_var.Index() == actual_var_idx:
                            if assumption_var in assumption_to_constraint:
                                c_id, atomic_idx = assumption_to_constraint[assumption_var]
                                core_constraints.append({
                                    "constraints_id": c_id,
                                    "atomic_index": atomic_idx
                                })
                                excluded_assumptions.append(assumption_var)
                            break
                
                logger.info(f"Found MUS core with {len(core_constraints)} conflicting constraints")
                all_conflict_constraints.extend(core_constraints)
                
                # Remove at least one assumption from the core to find other conflicts
                # Remove all from this core to find independent conflicts
                remaining_assumptions = [a for a in remaining_assumptions if a not in excluded_assumptions]
                
                if not remaining_assumptions:
                    logger.info("All assumptions exhausted")
                    break
            else:
                logger.error(f"Solver returned unexpected status: {status}")
                break
        
        # Build final result
        # Status is "failed" if:
        # 1. We found conflicting constraints during MUS detection, OR
        # 2. The final solver status is not successful (OPTIMAL/FEASIBLE)
        is_solver_successful = (status in (cp_model.OPTIMAL, cp_model.FEASIBLE)) if status is not None else False
        
        logger.info(f"MUS detection complete: found {len(all_conflict_constraints)} breaking atomic constraint(s)")
        if all_conflict_constraints:
            # Group by constraints_id for logging
            by_cid = {}
            for cc in all_conflict_constraints:
                cid = cc['constraints_id']
                if cid not in by_cid:
                    by_cid[cid] = []
                by_cid[cid].append(cc['atomic_index'])
            logger.info(f"Breaking constraints span {len(by_cid)} unique constraint IDs: {sorted(by_cid.keys())}")

        is_failed = bool(all_conflict_constraints) or not is_solver_successful
        result = {
            "status": "failed" if is_failed else "solved",
            "solution": [],
            "conflict_constraints": all_conflict_constraints,
            "used_constraint_ids": []
        }
        if is_failed:
            # Distinguish "user constraints conflict" (we have an MUS pointing
            # at relaxable assumptions) from "base model UNSAT" (no relaxable
            # constraint is to blame — system hard constraints alone are not
            # satisfiable). The pre-flight feasibility check above already
            # peeled off the structural "data_infeasible" case, so anything
            # reaching here is one of these two.
            result["failure_reason"] = (
                "user_constraints" if all_conflict_constraints else "base_model"
            )

        if result["status"] == "solved":
            logger.info(f"Solution found! Status: {status}")
            
            output_sessions = []
            for (oid, d), act_var in active.items():
                if solver.Value(act_var):
                    start_slot = solver.Value(starts[(oid, d)])
                    s_time = self._slot_to_time(start_slot)
                    duration = durations[oid]
                    e_time = self._slot_to_time(start_slot + duration)
                    
                    lects = offering_map[oid]['lecturers']
                    for lid in lects:
                        if lid is None: continue 
                        output_sessions.append({
                            "offering_id": oid,
                            "lecturer_id": lid,
                            "day_of_week": d,
                            "start_time": s_time,
                            "end_time": e_time
                        })
            result["solution"] = output_sessions
            
            # Track which constraints were successfully used in the solution
            # All constraints that were not in conflict_constraints were successfully applied
            used_constraint_ids = []
            for c_data in constraints_data:
                c_id = c_data.get('constraints_id')
                if c_id is not None:
                    used_constraint_ids.append(c_id)
            result["used_constraint_ids"] = used_constraint_ids
            logger.info(f"Successfully scheduled with {len(used_constraint_ids)} constraint(s)")
        else:
            logger.warning(
                f"All MUS cores identified: {len(all_conflict_constraints)} "
                f"breaking constraint(s) across {iteration} iterations"
            )
            
        return result
