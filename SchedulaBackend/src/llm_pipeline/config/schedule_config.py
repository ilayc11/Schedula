"""
Domain-specific configuration for the scheduling system
"""
from typing import List


class WorkScheduleConfig:
    """Domain-specific configuration for the scheduling system"""
    
    # Working days (Sunday=1 to Friday=6, NO Saturday)
    WORKING_DAYS = {
        "SUNDAY": 1,
        "MONDAY": 2,
        "TUESDAY": 3,
        "WEDNESDAY": 4,
        "THURSDAY": 5,
        "FRIDAY": 6
    }
    
    # Working hours (in minutes from midnight for easy comparison)
    STANDARD_START_HOUR = 8
    STANDARD_END_HOUR = 20
    FRIDAY_END_HOUR = 15
    
    # Time period definitions (hour-based)
    TIME_PERIODS = {
        "morning": (8, 12),
        "afternoon": (12, 16),
        "evening": (16, 20)
    }
    
    FRIDAY_TIME_PERIODS = {
        "morning": (8, 12),
        "afternoon": (12, 15)
        # No evening on Friday
    }
    
    @classmethod
    def is_valid_day(cls, day: int) -> bool:
        """Check if day is valid (1-6)"""
        return 1 <= day <= 6
    
    @classmethod
    def is_valid_time(cls, hour: int, day: int = None) -> bool:
        """Check if hour is within working hours"""
        if hour < cls.STANDARD_START_HOUR:
            return False
        
        if day == 6:  # Friday
            return hour <= cls.FRIDAY_END_HOUR
        
        return hour <= cls.STANDARD_END_HOUR
    
    @classmethod
    def get_all_working_days(cls) -> List[int]:
        """Get all working days as integers"""
        return list(range(1, 7))  # [1, 2, 3, 4, 5, 6]
