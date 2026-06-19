"""
Constraint conflict detection
"""
from typing import List, Dict, Any, Optional

from ..models.atomic_constraint import AtomicConstraint


class ConflictDetector:
    """Detects contradictory constraints"""
    
    @staticmethod
    def detect_conflicts(constraints: List[AtomicConstraint]) -> Dict[str, Any]:
        """
        Detect contradictory constraints.
        
        Returns:
        {
            "has_conflicts": bool,
            "conflicts": List[Dict],  # List of conflict descriptions
            "warnings": List[str]
        }
        """
        conflicts = []
        warnings = []
        
        # Check for obvious contradictions
        # Group constraints by days for easier comparison
        day_constraints: Dict[int, List[AtomicConstraint]] = {}
        
        for constraint in constraints:
            for day in constraint.days:
                if day not in day_constraints:
                    day_constraints[day] = []
                day_constraints[day].append(constraint)
        
        # Check each day for conflicts
        for day, day_cons in day_constraints.items():
            # Check if any constraints completely overlap on same day/time
            for i, c1 in enumerate(day_cons):
                for c2 in day_cons[i+1:]:
                    conflict = ConflictDetector._check_overlap(c1, c2, day)
                    if conflict:
                        conflicts.append(conflict)
        
        # Check for "cannot work any day" scenario
        all_days_blocked = all(
            day in day_constraints 
            for day in range(1, 7)
        )
        
        if all_days_blocked:
            # Check if ALL time slots are blocked for all days
            all_blocked = True
            for day in range(1, 7):
                day_cons = day_constraints.get(day, [])
                has_full_day_block = any(
                    ConflictDetector._is_full_day_block(c, day)
                    for c in day_cons
                )
                if not has_full_day_block:
                    all_blocked = False
                    break
            
            if all_blocked:
                warnings.append(
                    "All days are blocked - this constraint set may be impossible to satisfy"
                )
        
        return {
            "has_conflicts": len(conflicts) > 0,
            "conflicts": conflicts,
            "warnings": warnings
        }
    
    @staticmethod
    def _is_full_day_block(constraint: AtomicConstraint, day: int) -> bool:
        """Check if a constraint blocks the entire working day"""
        if not constraint.time_slot:
            return False
        
        start_mins, end_mins = constraint.time_slot.to_minutes()
        
        # Full-day for regular days: 8:00-20:00 (480-1200 minutes)
        # Full-day for Friday: 8:00-15:00 (480-900 minutes)
        if day == 6:  # Friday
            return start_mins == 480 and end_mins == 900  # 8:00-15:00
        else:
            return start_mins == 480 and end_mins == 1200  # 8:00-20:00
    
    @staticmethod
    def _check_overlap(c1: AtomicConstraint, c2: AtomicConstraint, day: int) -> Optional[Dict[str, Any]]:
        """Check if two constraints overlap and create conflict"""
        
        # Only care about overlapping days
        if day not in c1.days or day not in c2.days:
            return None
        
        # Check if either blocks the entire day
        c1_full_day = ConflictDetector._is_full_day_block(c1, day)
        c2_full_day = ConflictDetector._is_full_day_block(c2, day)
        
        # If both block the entire day, that's a duplication, not a conflict
        if c1_full_day and c2_full_day:
            return None
        
        # If one blocks entire day and other blocks specific time, that's redundant
        if c1_full_day or c2_full_day:
            return {
                "type": "redundancy",
                "constraint_ids": [c1.constraint_id, c2.constraint_id],
                "description": f"One constraint blocks entire day {day}, making the other redundant",
                "severity": "low"
            }
        
        # Check time overlap
        c1_start, c1_end = c1.time_slot.to_minutes()
        c2_start, c2_end = c2.time_slot.to_minutes()
        
        # Do they overlap?
        overlaps = not (c1_end <= c2_start or c2_end <= c1_start)
        
        if overlaps:
            return {
                "type": "time_overlap",
                "constraint_ids": [c1.constraint_id, c2.constraint_id],
                "description": f"Constraints overlap on day {day}: {c1.original_text[:40]} vs {c2.original_text[:40]}",
                "severity": "medium"
            }
        
        return None
