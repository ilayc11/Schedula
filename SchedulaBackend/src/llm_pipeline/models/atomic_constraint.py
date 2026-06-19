"""
Atomic constraint data model
"""
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from .enums import ConstraintType
from .time_slot import TimeSlot


@dataclass
class AtomicConstraint:
    """Represents a single atomic constraint with integer-based data"""
    constraint_id: str
    constraint_type: ConstraintType
    days: List[int]  # Integer day codes: 1=Sunday, 2=Monday, etc.
    time_slot: Optional[TimeSlot]  # Always present in practice; full-day blocks use full working hours
    priority: str  # "hard" or "soft"
    metadata: Dict[str, Any]
    original_text: str
    confidence_score: float
    
    def to_csp_format(self) -> Dict[str, Any]:
        """Convert to CSP solver input format (all integers)"""
        return {
            "id": self.constraint_id,
            "type": self.constraint_type.value,
            "days": self.days,  # Already integers
            "time_slot": self.time_slot.to_dict() if self.time_slot else None,
            "priority": self.priority,
            "metadata": self.metadata,
            "confidence": self.confidence_score
        }
    
    def to_storage_format(self) -> Dict[str, Any]:
        """Convert to simplified database storage format
        
        Excludes: constraint_id, priority (stored at row level), 
                  confidence_score, metadata (not needed for solver)
        """
        result = {
            "type": self.constraint_type.value,
            "days": self.days,
        }
        
        # Only include time_slot if it exists
        if self.time_slot:
            result["time_slot"] = {
                "start_hour": self.time_slot.start_hour,
                "end_hour": self.time_slot.end_hour
            }
        else:
            result["time_slot"] = None
            
        return result