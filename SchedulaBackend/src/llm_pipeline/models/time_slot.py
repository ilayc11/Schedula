"""
Time slot data model
"""
from dataclasses import dataclass
from typing import Tuple, Dict


@dataclass
class TimeSlot:
    """Represents a time slot with integer hours/minutes"""
    start_hour: int  # 0-23
    start_minute: int  # 0-59
    end_hour: int  # 0-23
    end_minute: int  # 0-59
    
    def to_minutes(self) -> Tuple[int, int]:
        """Convert to minutes from midnight for easy comparison"""
        return (
            self.start_hour * 60 + self.start_minute,
            self.end_hour * 60 + self.end_minute
        )
    
    def to_dict(self) -> Dict[str, int]:
        """Convert to simple dict"""
        return {
            "start_hour": self.start_hour,
            "start_minute": self.start_minute,
            "end_hour": self.end_hour,
            "end_minute": self.end_minute
        }
