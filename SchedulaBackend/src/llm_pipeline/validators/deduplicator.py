"""
Constraint deduplication - SIMPLIFIED
Removes merger class - conflict handler does that work now
"""
from typing import List, Dict, Any, Set

from ..models.atomic_constraint import AtomicConstraint


class ConstraintDeduplicator:
    """
    Removes duplicate atomic constraints using set-like behavior.
    
    Two constraints are considered duplicates if they have:
    - Same days
    - Same time slot (or both None)
    - Same priority
    """
    
    @staticmethod
    def _constraint_to_key(constraint: AtomicConstraint) -> tuple:
        """
        Convert constraint to hashable key for deduplication.
        """
        # Sort days for consistent comparison
        days_key = tuple(sorted(constraint.days))
        
        # Convert time_slot to tuple or None
        if constraint.time_slot:
            time_key = (
                constraint.time_slot.start_hour,
                constraint.time_slot.start_minute,
                constraint.time_slot.end_hour,
                constraint.time_slot.end_minute
            )
        else:
            time_key = None
        
        # Priority
        priority_key = constraint.priority
        
        return (days_key, time_key, priority_key)
    
    @staticmethod
    def deduplicate(constraints: List[AtomicConstraint]) -> List[AtomicConstraint]:
        """
        Remove duplicate constraints, keeping only the first occurrence.
        
        Args:
            constraints: List of atomic constraints (may contain duplicates)
        
        Returns:
            List of unique atomic constraints
        """
        seen_keys: Set[tuple] = set()
        unique_constraints = []
        
        for constraint in constraints:
            key = ConstraintDeduplicator._constraint_to_key(constraint)
            
            if key not in seen_keys:
                seen_keys.add(key)
                unique_constraints.append(constraint)
        
        return unique_constraints
    
    @staticmethod
    def get_duplicate_report(constraints: List[AtomicConstraint]) -> Dict[str, Any]:
        """
        Generate a report about duplicates (for debugging).
        
        Returns:
            {
                "total": int,
                "unique": int,
                "duplicates_removed": int,
                "duplicate_groups": List[Dict]
            }
        """
        key_to_constraints: Dict[tuple, List[AtomicConstraint]] = {}
        
        for constraint in constraints:
            key = ConstraintDeduplicator._constraint_to_key(constraint)
            if key not in key_to_constraints:
                key_to_constraints[key] = []
            key_to_constraints[key].append(constraint)
        
        duplicate_groups = []
        for key, group in key_to_constraints.items():
            if len(group) > 1:
                duplicate_groups.append({
                    "key": key,
                    "count": len(group),
                    "constraint_ids": [c.constraint_id for c in group]
                })
        
        return {
            "total": len(constraints),
            "unique": len(key_to_constraints),
            "duplicates_removed": len(constraints) - len(key_to_constraints),
            "duplicate_groups": duplicate_groups
        }