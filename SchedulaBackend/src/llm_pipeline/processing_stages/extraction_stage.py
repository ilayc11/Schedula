"""
Stage 4: Extraction - Extract days and time slots
"""
from typing import Dict, Any, Optional

from .base_stage import BaseStage
from ..llm.interface import LLMInterface
from ..models.time_slot import TimeSlot


class ExtractionStage(BaseStage):
    """Stage 4: Extract days (as integers) and time slots - FIXED VERSION"""
    
    def __init__(self, llm: LLMInterface):
        super().__init__(llm, "extraction")
    
    async def process(self, constraint_text: str) -> Dict[str, Any]:
        """Extract days (as integers) and times - FIXED VERSION with text-based validation"""
        print(f"\n{'='*80}")
        print(f"🔹 STAGE 4: EXTRACTION (FIXED - Correct Time Periods)")
        print(f"{'='*80}")
        print(f"Constraint: \"{constraint_text}\"")
        
        prompt = f"""Constraint: "{constraint_text}"

Extract (days as INTEGER codes 1-6, Thursday=5, afternoon end_hour=16):"""
        
        print(f"⏳ Calling LLM for extraction...")
        response = await self.llm.call(prompt, self.system_prompt)
        
        try:
            result = self._parse_json(response, default={
                "days": [],
                "time_slot": None,
                "confidence": 0.2
            })
            
            days = result.get('days', [])
            if not days or len(days) == 0:
                print(f"⚠️  No specific days mentioned")
                print(f"   Defaulting to ALL working days (Sun-Fri)")
                days = [1, 2, 3, 4, 5, 6]
                result['days'] = days
            
            # Validate and correct Friday afternoon times if needed
            time_slot_dict = result.get('time_slot')
            time_slot_obj: Optional[TimeSlot] = None
            
            # If time_slot is null/None, create full-day time slot based on day(s)
            if time_slot_dict is None:
                days_final = result.get('days', [])
                # Check if blocking Friday (use 15:00 end) or other days (use 20:00 end)
                # If multiple days including Friday, we'll use the appropriate end for each
                # For simplicity, if ALL days are Friday, use 15:00, otherwise use 20:00
                if days_final == [6]:
                    # Friday only - ends at 15:00
                    time_slot_dict = {
                        "start_hour": 8,
                        "start_minute": 0,
                        "end_hour": 15,
                        "end_minute": 0
                    }
                    print(f"⚠️  Full-day block detected - using Friday hours (08:00-15:00)")
                else:
                    # Regular days - ends at 20:00
                    time_slot_dict = {
                        "start_hour": 8,
                        "start_minute": 0,
                        "end_hour": 20,
                        "end_minute": 0
                    }
                    print(f"⚠️  Full-day block detected - using regular hours (08:00-20:00)")
            
            if time_slot_dict:
                # If this looks like afternoon (starts at 13:00)
                if time_slot_dict.get('start_hour') == 13:
                    days_final = result.get('days', [])
                    
                    # If it IS Friday (only), force end to 15
                    if days_final == [6]:
                        if time_slot_dict.get('end_hour') != 15:
                            print(f"⚠️  WARNING: Correcting Friday afternoon end_hour to 15")
                            time_slot_dict['end_hour'] = 15
                    
                    # If it's NOT only Friday, and end_hour is 15, correct it to 16
                    elif time_slot_dict.get('end_hour') == 15:
                        print(f"⚠️  WARNING: Correcting afternoon end_hour from 15 to 16")
                        time_slot_dict['end_hour'] = 16
                
                # Convert dict to TimeSlot object
                time_slot_obj = TimeSlot(
                    start_hour=time_slot_dict.get('start_hour', 0),
                    start_minute=time_slot_dict.get('start_minute', 0),
                    end_hour=time_slot_dict.get('end_hour', 0),
                    end_minute=time_slot_dict.get('end_minute', 0)
                )
            
            print(f"✅ Extraction complete:")
            print(f"   Days (integers): {result.get('days', [])}")
            if time_slot_obj:
                print(f"   Time: {time_slot_obj.start_hour:02d}:{time_slot_obj.start_minute:02d} - {time_slot_obj.end_hour:02d}:{time_slot_obj.end_minute:02d}")
            print(f"   Confidence: {result.get('confidence', 0):.2f}")
            
            return {
                "days": result.get('days', []),
                "time_slot": time_slot_obj,
                "confidence": result.get('confidence', 0.5)
            }
            
        except Exception as e:
            print(f"❌ Error: {e}")
            return {
                "days": [],
                "time_slot": None,
                "confidence": 0.2
            }
