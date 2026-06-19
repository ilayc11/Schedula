"""
Rule-based validation - no LLM required
"""
from typing import Dict, Any, List

from ..config.schedule_config import WorkScheduleConfig


class RuleBasedValidator:
    """
    Fast, deterministic validation using hard-coded rules
    NO LLM NEEDED - just pure logic
    """
    
    @staticmethod
    def validate(constraint_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate constraint data using rules
        
        Returns:
        {
            "is_valid": bool,
            "issues": List[str],
            "suggestions": List[str]
        }
        """
        print(f"\n{'='*80}")
        print(f"🔹 STAGE 5: RULE-BASED VALIDATION")
        print(f"{'='*80}")
        
        issues: List[str] = []
        suggestions: List[str] = []
        
        days = constraint_data.get("days", [])
        time_slot = constraint_data.get("time_slot")
        priority = constraint_data.get("priority")
        
        # Rule 0: Validate priority
        print(f"⚙️  Rule 0: Checking priority validity...")
        if priority and priority not in ["hard", "soft"]:
            issues.append(f"Invalid priority '{priority}'. Must be 'hard' or 'soft'")
            suggestions.append("Use 'hard' for strict constraints or 'soft' for preferences")
            print(f"   ❌ Invalid priority: {priority}")
        else:
            print(f"   ✓ Priority is valid: {priority}")
        
        print(f"Validating: days={days}, time_slot={'present' if time_slot else 'None (all day)'}, priority={priority}")
        
        # Extract time values once at the beginning
        start_hour = None
        start_minute = None
        end_hour = None
        end_minute = None
        
        if time_slot:
            # Handle both TimeSlot objects and dicts for backward compatibility
            if hasattr(time_slot, 'start_hour'):
                # TimeSlot object
                start_hour = time_slot.start_hour
                start_minute = time_slot.start_minute
                end_hour = time_slot.end_hour
                end_minute = time_slot.end_minute
            elif isinstance(time_slot, dict):
                start_hour = time_slot.get("start_hour")
                start_minute = time_slot.get("start_minute")
                end_hour = time_slot.get("end_hour")
                end_minute = time_slot.get("end_minute")
            
            print(f"   Time slot: {start_hour:02d}:{start_minute:02d} - {end_hour:02d}:{end_minute:02d}")
        
        # Rule 1: Check days are valid (1-6, no 0 or 7=Saturday)
        print(f"⚙️  Rule 1: Checking days are valid (1-6, no Saturday)...")
        for day in days:
            if not isinstance(day, int):
                issues.append(f"Day '{day}' is not an integer")
                suggestions.append("Days must be integers 1-6")
                print(f"   ❌ Day '{day}' is not an integer")
                continue
            
            if day == 0 or day == 7:
                issues.append("Saturday (day 0 or 7) is not a working day")
                suggestions.append("Remove Saturday from constraint")
                print(f"   ❌ Saturday (day {day}) is not allowed")
            elif not (1 <= day <= 6):
                issues.append(f"Day {day} is out of valid range (1-6)")
                suggestions.append("Days must be 1=Sunday through 6=Friday")
                print(f"   ❌ Day {day} out of range")
            else:
                print(f"   ✓ Day {day} is valid")
        
        # Rule 2: Check time slots if present
        if time_slot:
            print(f"⚙️  Rule 2: Checking time slot validity...")
            
            # Time values already extracted above
            
            # Sub-rule 2a: Times must be integers
            if not all(isinstance(x, int) for x in [start_hour, end_hour, start_minute, end_minute]):
                issues.append("Time values must be integers")
                suggestions.append("Use integer hours (0-23) and minutes (0-59)")
                print(f"   ❌ Time values must be integers")
            
            else:
                # Sub-rule 2b: End must be after start
                start_mins = start_hour * 60 + start_minute
                end_mins = end_hour * 60 + end_minute
                
                if end_mins <= start_mins:
                    issues.append(f"End time {end_hour}:{end_minute:02d} must be after start time {start_hour}:{start_minute:02d}")
                    suggestions.append("Swap start and end times or correct the constraint")
                    print(f"   ❌ End time must be after start time")
                else:
                    print(f"   ✓ End time ({end_hour}:{end_minute:02d}) is after start time ({start_hour}:{start_minute:02d})")
                
                # Sub-rule 2c: Check working hours
                if start_hour < WorkScheduleConfig.STANDARD_START_HOUR:
                    issues.append(f"Start hour {start_hour} is before working hours start (08:00)")
                    suggestions.append(f"Adjust start time to {WorkScheduleConfig.STANDARD_START_HOUR}:00 or later")
                    print(f"   ❌ Start hour {start_hour} is before 08:00")
                else:
                    print(f"   ✓ Start hour {start_hour} is within working hours")
                
                # Sub-rule 2d: Check Friday special case
                for day in days:
                    if day == 6:  # Friday
                        print(f"   ⚙️  Friday detected - checking 15:00 limit...")
                        if end_hour > WorkScheduleConfig.FRIDAY_END_HOUR:
                            issues.append(f"Friday ends at {WorkScheduleConfig.FRIDAY_END_HOUR}:00, but constraint goes until {end_hour}:{end_minute:02d}")
                            suggestions.append(f"Adjust Friday end time to {WorkScheduleConfig.FRIDAY_END_HOUR}:00 or earlier")
                            print(f"   ❌ Friday end time {end_hour}:{end_minute:02d} exceeds 15:00 limit")
                        else:
                            print(f"   ✓ Friday time is within 15:00 limit")
                        
                        # Check for evening on Friday
                        if start_hour >= 16:
                            issues.append("Friday has no evening hours (ends at 15:00)")
                            suggestions.append("Remove Friday from evening constraints")
                            print(f"   ❌ Friday has no evening hours")
                    
                    else:  # Other days
                        if end_hour > WorkScheduleConfig.STANDARD_END_HOUR:
                            issues.append(f"End hour {end_hour} exceeds working hours (20:00)")
                            suggestions.append(f"Adjust end time to {WorkScheduleConfig.STANDARD_END_HOUR}:00 or earlier")
                            print(f"   ❌ End hour {end_hour} exceeds 20:00")
                        else:
                            print(f"   ✓ Time is within working hours for day {day}")
        
        # Rule 3: At least one day must be specified
        print(f"⚙️  Rule 3: Checking at least one day is specified...")
        if not days or len(days) == 0:
            issues.append("No days specified in constraint")
            suggestions.append("Add at least one day (1-6)")
            print(f"   ❌ No days specified")
        else:
            print(f"   ✓ {len(days)} day(s) specified")
        
        is_valid = len(issues) == 0
        
        if is_valid:
            print(f"\n✅ VALIDATION PASSED")
        else:
            print(f"\n❌ VALIDATION FAILED")
            print(f"   Issues: {len(issues)}")
            for issue in issues:
                print(f"   - {issue}")
        
        return {
            "is_valid": is_valid,
            "issues": issues,
            "suggestions": suggestions
        }
