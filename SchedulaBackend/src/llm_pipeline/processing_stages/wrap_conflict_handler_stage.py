"""
WRAP V5.1 - Specificity-Based Conflict Resolution with Rule-Based Boundary Detection
Core Principle: PARTIAL TIME > FULL DAY (Specificity Wins)

V5.1 Changes:
- Added rule-based boundary detection (before LLM validation)
- Enhanced validation prompt with explicit boundary examples
- Added post-LLM boundary override as safety net
- Only changed boundary-related logic, all other V5.0 features unchanged
"""
import json
import re
from typing import List, Dict, Any, Optional, Tuple, Set
from datetime import datetime

from .base_stage import BaseStage


class WrapConflictHandlerStage(BaseStage):
    """
    V5.1: Specificity-Based Priority System + Rule-Based Boundary Detection
    
    Conflict Resolution Rules:
    1. PARTIAL TIME > FULL DAY (always keep more specific)
    2. Same specificity → keep newer (most recent user intent)
    3. Different days → no conflict
    4. Boundaries (touching times) → ALWAYS keep (rule-based, not LLM)
    """
    
    BATCH_SIZE = 5
    
    def __init__(self, llm):
        super().__init__(llm, "merge_validation")
        # Note: self.system_prompt is now loaded from merge_validation.txt
    
    def _extract_days_from_text(self, text: str) -> List[int]:
        """Extract day numbers from text"""
        days = []
        text_lower = text.lower()
        
        day_map = {
            'sunday': 1, 'sun': 1,
            'monday': 2, 'mon': 2,
            'tuesday': 3, 'tue': 3, 'tues': 3,
            'wednesday': 4, 'wed': 4,
            'thursday': 5, 'thu': 5, 'thur': 5, 'thurs': 5,
            'friday': 6, 'fri': 6
        }
        
        for day_name, day_num in day_map.items():
            if day_name in text_lower:
                if day_num not in days:
                    days.append(day_num)
        
        return sorted(days)
    
    def _extract_time_from_text(self, text: str) -> Optional[Tuple[int, int]]:
        """
        Extract time range from text.
        Returns: (start_hour, end_hour) or None
        """
        time_pattern = r'(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})'
        match = re.search(time_pattern, text)
        
        if match:
            start_hour = int(match.group(1))
            end_hour = int(match.group(3))
            return (start_hour, end_hour)
        
        return None
    
    def _is_boundary_case(self, atomic: Dict, source_original: str) -> bool:
        """
        RULE-BASED BOUNDARY DETECTION (New in V5.1)
        
        Check if atomic is a boundary case (touches but doesn't overlap).
        Boundary cases should ALWAYS be kept.
        
        A boundary exists when:
        - Atomic ends exactly when original starts (before boundary)
        - Atomic starts exactly when original ends (after boundary)
        
        Returns: True if this is a boundary case that should be kept
        """
        # Extract original time range
        orig_time = self._extract_time_from_text(source_original)
        if not orig_time:
            return False  # Original has no time, can't be boundary
        
        orig_start, orig_end = orig_time
        
        # Extract atomic time range
        atomic_time = atomic.get('time_slot')
        if not atomic_time:
            return False  # Atomic has no time (full day), can't be boundary
        
        atomic_start = atomic_time.get('start_hour')
        atomic_end = atomic_time.get('end_hour')
        
        if atomic_start is None or atomic_end is None:
            return False
        
        # Check for boundary conditions
        # Case 1: Atomic ends where original starts (BEFORE boundary)
        # Example: atomic 08:00-10:00, original 10:00-19:00
        if atomic_end == orig_start:
            return True
        
        # Case 2: Atomic starts where original ends (AFTER boundary)
        # Example: atomic 19:00-20:00, original 10:00-19:00
        if atomic_start == orig_end:
            return True
        
        return False
    
    def _has_time_slot(self, atomic: Dict) -> bool:
        """Check if atomic has a specific time slot (not full-day)"""
        time_slot = atomic.get("time_slot")
        if not time_slot:
            return False
        
        # Check if it's a full-day block based on time values
        day = atomic.get("days", [None])[0] if atomic.get("days") else None
        if not day:
            return True  # If no day info, assume it's specific
        
        # Get time in minutes
        if isinstance(time_slot, dict):
            start_mins = time_slot.get("start_hour", 0) * 60 + time_slot.get("start_minute", 0)
            end_mins = time_slot.get("end_hour", 0) * 60 + time_slot.get("end_minute", 0)
        else:
            start_mins = time_slot.start_hour * 60 + getattr(time_slot, 'start_minute', 0)
            end_mins = time_slot.end_hour * 60 + getattr(time_slot, 'end_minute', 0)
        
        # Check if it's a full-day block (8:00-20:00 or 8:00-15:00 for Friday)
        if day == 6:  # Friday
            is_full_day = (start_mins == 480 and end_mins == 900)  # 8:00-15:00
        else:
            is_full_day = (start_mins == 480 and end_mins == 1200)  # 8:00-20:00
        
        return not is_full_day  # Return True if NOT a full-day block
    
    def _get_specificity_level(self, atomic: Dict) -> int:
        """
        Get specificity level (lower number = more specific = higher priority)
        1 = Partial time (most specific)
        2 = Full day (less specific)
        """
        return 1 if self._has_time_slot(atomic) else 2
    
    def _format_atomic(self, atomic) -> Dict:
        """Format atomic constraint for LLM"""
        time_slot = None
        if hasattr(atomic, 'time_slot') and atomic.time_slot:
            if isinstance(atomic.time_slot, dict):
                time_slot = atomic.time_slot
            else:
                time_slot = {
                    "start_hour": atomic.time_slot.start_hour,
                    "start_minute": getattr(atomic.time_slot, 'start_minute', 0),
                    "end_hour": atomic.time_slot.end_hour,
                    "end_minute": getattr(atomic.time_slot, 'end_minute', 0)
                }
        elif isinstance(atomic, dict) and atomic.get('time_slot'):
            time_slot = atomic.get('time_slot')
        
        # Handle both object attributes and dictionary keys for constraint_id
        constraint_id = "unknown"
        if hasattr(atomic, 'constraint_id'):
            constraint_id = atomic.constraint_id
        elif isinstance(atomic, dict):
            constraint_id = atomic.get('constraint_id', 'unknown')
        
        # Handle days field
        if hasattr(atomic, 'days'):
            days = atomic.days
        elif isinstance(atomic, dict):
            days = atomic.get('days', [])
        else:
            days = []
        
        # Handle text/original_text field
        if hasattr(atomic, 'original_text'):
            text = atomic.original_text
        elif isinstance(atomic, dict):
            text = atomic.get('text', atomic.get('original_text', ''))
        else:
            text = ''
        
        return {
            "id": constraint_id,
            "days": days,
            "time_slot": time_slot,
            "text": text,
        }
    
    def _check_specificity_conflict(
        self,
        atomic1: Dict,
        atomic2: Dict
    ) -> Optional[Tuple[str, str]]:
        """
        Check if two atomics conflict based on specificity.
        Returns: (id_to_remove, reason) or None if no conflict
        
        Rule: If same day, PARTIAL TIME > FULL DAY
        """
        days1 = set(atomic1.get('days', []))
        days2 = set(atomic2.get('days', []))
        
        # Different days → no conflict
        if not (days1 & days2):
            return None
        
        has_time1 = self._has_time_slot(atomic1)
        has_time2 = self._has_time_slot(atomic2)
        
        # Both have same specificity → no conflict (let LLM decide)
        if has_time1 == has_time2:
            return None
        
        # One is partial, one is full-day → partial wins
        if has_time1 and not has_time2:
            # atomic1 is more specific, remove atomic2
            return (atomic2['id'], f"Full-day block superseded by more specific partial-time constraint {atomic1['id']}")
        
        if not has_time1 and has_time2:
            # atomic2 is more specific, remove atomic1
            return (atomic1['id'], f"Full-day block superseded by more specific partial-time constraint {atomic2['id']}")
        
        return None
    
    def _find_specificity_conflicts(
        self,
        atomics: List[Dict]
    ) -> Dict[str, str]:
        """
        Find all specificity-based conflicts.
        Returns: {constraint_id: reason} for all atomics to remove
        """
        print(f"\n{'='*80}")
        print(f"🔍 SPECIFICITY-BASED CONFLICT DETECTION")
        print(f"{'='*80}")
        print(f"Checking {len(atomics)} atomics for full-day vs partial-time conflicts...")
        
        to_remove = {}
        
        for i, atomic1 in enumerate(atomics):
            if atomic1['id'] in to_remove:
                continue
                
            for j, atomic2 in enumerate(atomics):
                if i >= j or atomic2['id'] in to_remove:
                    continue
                
                conflict = self._check_specificity_conflict(atomic1, atomic2)
                if conflict:
                    id_to_remove, reason = conflict
                    if id_to_remove not in to_remove:
                        to_remove[id_to_remove] = reason
                        
                        # Determine which is which
                        if id_to_remove == atomic1['id']:
                            kept, removed = atomic2, atomic1
                        else:
                            kept, removed = atomic1, atomic2
                        
                        print(f"  ⚠️  CONFLICT DETECTED:")
                        print(f"      Day(s): {removed['days']}")
                        print(f"      KEPT:    {kept['id']} (partial-time: {self._has_time_slot(kept)})")
                        print(f"      REMOVED: {removed['id']} (partial-time: {self._has_time_slot(removed)})")
                        print(f"      Reason: {reason}")
        
        if not to_remove:
            print(f"  ✅ No specificity conflicts found")
        else:
            print(f"  📊 Total conflicts: {len(to_remove)}")
        
        return to_remove
    
    async def validate_batch_against_originals(
        self,
        batch: List[Dict],
        source_originals_map: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """
        Validate atomics against their SOURCE originals only.
        Each atomic is only checked against the original that created it.
        
        V5.1 CHANGE: Added rule-based boundary detection before LLM validation
        """
        decisions = []
        needs_llm = []
        
        print(f"  [Quick rule check for {len(batch)} atomics...]")
        
        for atomic in batch:
            atomic_id = atomic["id"]
            source_original = source_originals_map.get(atomic_id)
            
            if not source_original:
                # No source original → keep (shouldn't happen)
                decisions.append({
                    "constraint_id": atomic_id,
                    "contradicts": False,
                    "decision": "KEEP",
                    "reasoning": "No source original found (default KEEP)"
                })
                print(f"    ⚠️  {atomic_id}: KEEP (no source)")
                continue
            
            # Extract days from source original
            orig_days = set(self._extract_days_from_text(source_original))
            atomic_days = set(atomic["days"])
            
            # Rule 1: Different days → KEEP (100% reliable)
            if not (atomic_days & orig_days):
                decisions.append({
                    "constraint_id": atomic_id,
                    "contradicts": False,
                    "decision": "KEEP",
                    "reasoning": f"Days {atomic['days']} different from source original (rule-based)"
                })
                print(f"    ✓ {atomic_id}: KEEP (different days, rule-based)")
                continue
            
            # Rule 2: Boundary case → KEEP (NEW IN V5.1 - 100% reliable)
            if self._is_boundary_case(atomic, source_original):
                decisions.append({
                    "constraint_id": atomic_id,
                    "contradicts": False,
                    "decision": "KEEP",
                    "reasoning": "Boundary case - touches but doesn't overlap with availability (rule-based)"
                })
                print(f"    ✓ {atomic_id}: KEEP (boundary case, rule-based)")
                continue
            
            # Same day and not boundary → needs LLM (complex time logic)
            needs_llm.append(atomic)
            print(f"    → {atomic_id}: needs LLM (same day, not boundary)")
        
        # If all were handled by rules, return
        if not needs_llm:
            return decisions
        
        # Call LLM for complex same-day validation
        print(f"  [Calling LLM for {len(needs_llm)} same-day validation(s)...]")
        
        # Group by source original for LLM call
        grouped = {}
        for atomic in needs_llm:
            source = source_originals_map[atomic["id"]]
            if source not in grouped:
                grouped[source] = []
            grouped[source].append(atomic)
        
        # Call LLM for each source group
        for source_original, atomics_group in grouped.items():
            prompt = f"""ATOMIC CONSTRAINTS TO VALIDATE ({len(atomics_group)} constraints):
{json.dumps(atomics_group, indent=2)}

ORIGINAL USER STATEMENT:
"{source_original}"

For EACH atomic constraint above, decide KEEP or REMOVE.
Only check if the atomic contradicts THIS specific original statement.

Remember:
- If original = "I CAN work X" and atomic blocks X → REMOVE (contradiction)
- If original = "I CANNOT work X" and atomic blocks X → KEEP (agreement)
- Boundaries (times that touch but don't overlap) → KEEP
- Different days/times → KEEP

Return a JSON array with one decision per constraint (same order as input).
NO markdown, NO code fences, ONLY the JSON array.
"""

            try:
                response = await self.llm.call(prompt, self.system_prompt)
                
                # Clean response
                response = response.replace('```json', '').replace('```', '').strip()
                array_match = re.search(r'\[[\s\S]*\]', response)
                if array_match:
                    response = array_match.group(0)
                
                llm_decisions = json.loads(response)
                
                # Validate count
                if len(llm_decisions) != len(atomics_group):
                    print(f"    ⚠️  Expected {len(atomics_group)} decisions, got {len(llm_decisions)}")
                    while len(llm_decisions) < len(atomics_group):
                        llm_decisions.append({
                            "constraint_id": atomics_group[len(llm_decisions)]["id"],
                            "contradicts": False,
                            "decision": "KEEP",
                            "reasoning": "Error: defaulting to KEEP"
                        })
                
                # V5.1 SAFETY NET: Override LLM if it wrongly removes boundary cases
                for decision in llm_decisions:
                    atomic = next(a for a in atomics_group if a['id'] == decision['constraint_id'])
                    source = source_originals_map[atomic['id']]
                    
                    if decision['decision'] == 'REMOVE' and self._is_boundary_case(atomic, source):
                        print(f"    ⚠️  LLM incorrectly removed boundary case {atomic['id']}")
                        print(f"        Overriding to KEEP (boundary safety net)")
                        decision['decision'] = 'KEEP'
                        decision['reasoning'] = 'Boundary case - touches but doesn\'t overlap (LLM override)'
                
                # Log LLM decisions
                for decision in llm_decisions:
                    action = decision['decision']
                    print(f"    ✓ {decision['constraint_id']}: {action} (LLM)")
                
                decisions.extend(llm_decisions)
                
            except Exception as e:
                print(f"    ⚠️  LLM error: {e}")
                if 'response' in locals():
                    print(f"        Response: {response[:300]}")
                
                # Default to KEEP on error (safer)
                for atomic in atomics_group:
                    decisions.append({
                        "constraint_id": atomic["id"],
                        "contradicts": False,
                        "decision": "KEEP",
                        "reasoning": f"Error, defaulting to KEEP: {str(e)}"
                    })
        
        return decisions
    
    async def process(
        self,
        current_constraints: List,
        current_original_text: str,
        previous_constraints: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        V5.1: Specificity-based conflict resolution + Rule-based boundary detection
        
        Algorithm:
        1. Collect all atomics (old + new) with source tracking
        2. Remove exact duplicates
        3. Apply specificity-based conflict resolution (PARTIAL > FULL)
        4. Validate atomics against their source originals:
           - Rule-based: different days → KEEP
           - Rule-based: boundary cases → KEEP (NEW IN V5.1)
           - LLM: complex same-day conflicts
           - Safety net: override LLM if it removes boundaries
        5. Build merged output
        """
        print(f"\n{'='*80}")
        print(f"🔍 WRAP V5.1 - Specificity + Rule-Based Boundary Detection")
        print(f"{'='*80}")
        print(f"Current input: \"{current_original_text}\"")
        print(f"New atomics: {len(current_constraints)}")
        print(f"Previous constraints: {len(previous_constraints)}")
        print(f"Batch size: {self.BATCH_SIZE}")
        
        # Collect ALL originals and ALL atomics with source tracking
        all_originals = []
        all_atomics_list = []
        source_originals_map = {}  # atomic_id -> source_original_text
        
        # Previous
        for prev in previous_constraints:
            prev_original = prev.get("text", "")
            if prev_original:
                all_originals.append(prev_original)
            
            metadata = prev.get("metadata", {})
            for ac in metadata.get("atomic_constraints", []):
                atomic_dict = {
                    "id": ac.get("constraint_id", "unknown"),
                    "days": ac.get("days", []),
                    "time_slot": ac.get("time_slot"),
                    "text": ac.get("original_text", ""),
                }
                all_atomics_list.append({
                    "atomic": atomic_dict,
                    "source": "previous",
                    "source_original": prev_original
                })
                source_originals_map[atomic_dict["id"]] = prev_original
        
        # Current
        all_originals.append(current_original_text)
        
        for atomic in current_constraints:
            atomic_dict = self._format_atomic(atomic)
            all_atomics_list.append({
                "atomic": atomic_dict,
                "source": "current",
                "source_original": current_original_text
            })
            source_originals_map[atomic_dict["id"]] = current_original_text
        
        print(f"\n📊 Collected:")
        print(f"  Originals: {len(all_originals)}")
        for i, orig in enumerate(all_originals, 1):
            print(f"    {i}. \"{orig}\"")
        print(f"  Atomics: {len(all_atomics_list)}")
        
        # STEP 1: Deduplication
        print(f"\n{'='*80}")
        print(f"STEP 1: Deduplication")
        print(f"{'='*80}")
        
        seen = {}
        unique_atomics = []
        duplicates_removed = []
        
        for item in all_atomics_list:
            atomic = item["atomic"]
            key = (tuple(atomic["days"]), 
                   tuple(atomic["time_slot"].items()) if atomic["time_slot"] else None,
                   atomic["text"])
            
            if key in seen:
                dup_id = seen[key]
                print(f"  ❌ {atomic['id']}: Duplicate of {dup_id}")
                duplicates_removed.append({
                    "id": atomic["id"],
                    "source": item["source"],
                    "reason": f"Duplicate of {dup_id}"
                })
            else:
                seen[key] = atomic["id"]
                unique_atomics.append(item)
        
        print(f"  Removed: {len(duplicates_removed)} duplicates")
        print(f"  Remaining: {len(unique_atomics)} unique atomics")
        
        # STEP 2: Specificity-based conflict resolution
        atomics_only = [item["atomic"] for item in unique_atomics]
        specificity_conflicts = self._find_specificity_conflicts(atomics_only)
        
        # Remove specificity conflicts
        atomics_after_specificity = []
        invalid_specificity = []
        
        for item in unique_atomics:
            atomic_id = item["atomic"]["id"]
            if atomic_id in specificity_conflicts:
                invalid_specificity.append({
                    "id": atomic_id,
                    "source": item["source"],
                    "reason": specificity_conflicts[atomic_id]
                })
                print(f"  ❌ Removing {atomic_id}: {specificity_conflicts[atomic_id]}")
            else:
                atomics_after_specificity.append(item)
        
        print(f"\n  After specificity resolution: {len(atomics_after_specificity)} kept, {len(invalid_specificity)} removed")
        
        # STEP 3: LLM Validation (batched, source-aware, with rule-based boundary detection)
        print(f"\n{'='*80}")
        print(f"STEP 3: LLM Validation (Source-Aware + Boundary Rules)")
        print(f"{'='*80}")
        
        valid_atomics_final = []
        invalid_atomics_llm = []
        
        total_batches = (len(atomics_after_specificity) + self.BATCH_SIZE - 1) // self.BATCH_SIZE
        
        for batch_idx in range(total_batches):
            start_idx = batch_idx * self.BATCH_SIZE
            end_idx = min(start_idx + self.BATCH_SIZE, len(atomics_after_specificity))
            batch = [item["atomic"] for item in atomics_after_specificity[start_idx:end_idx]]
            
            print(f"\n  Batch {batch_idx + 1}/{total_batches}: Atomics {start_idx + 1}-{end_idx}")
            
            decisions = await self.validate_batch_against_originals(batch, source_originals_map)
            
            for i, decision in enumerate(decisions):
                item = atomics_after_specificity[start_idx + i]
                atomic = item["atomic"]
                
                print(f"    [{start_idx + i + 1}] {atomic['id']}: {decision['decision']}")
                print(f"        {decision['reasoning']}")
                
                if decision["decision"] == "KEEP":
                    valid_atomics_final.append(item)
                else:
                    invalid_atomics_llm.append({
                        "id": atomic["id"],
                        "source": item["source"],
                        "reason": decision["reasoning"]
                    })
        
        print(f"\n  After LLM validation: {len(valid_atomics_final)} kept, {len(invalid_atomics_llm)} removed")
        
        # STEP 4: Build merged constraint
        print(f"\n{'='*80}")
        print(f"🔗 Building Merged Constraint")
        print(f"{'='*80}")
        
        merged_atomics = []
        for item in valid_atomics_final:
            merged_atomics.append({
                "source": item["source"],
                "original_text": item["source_original"],
                "atomic": item["atomic"]
            })
        
        old_count = sum(1 for a in valid_atomics_final if a['source'] == 'previous')
        new_count = sum(1 for a in valid_atomics_final if a['source'] == 'current')
        
        all_invalid = duplicates_removed + invalid_specificity + invalid_atomics_llm
        
        print(f"\n📊 Final Summary:")
        print(f"  Originals: {len(all_originals)}")
        print(f"  Valid atomics: {len(valid_atomics_final)}")
        print(f"    - From previous: {old_count}")
        print(f"    - From current: {new_count}")
        print(f"  Removed: {len(all_invalid)}")
        print(f"    - Duplicates: {len(duplicates_removed)}")
        print(f"    - Specificity conflicts: {len(invalid_specificity)}")
        print(f"    - Invalid (LLM): {len(invalid_atomics_llm)}")
        
        merged_constraint = {
            "original_texts": all_originals,
            "atomic_constraints": merged_atomics,
            "created_at": datetime.now().isoformat(),
            "metadata": {
                "total_atomics": len(valid_atomics_final),
                "sources": {
                    "previous": old_count,
                    "current": new_count
                },
                "validation_stats": {
                    "total_validated": len(all_atomics_list),
                    "kept": len(valid_atomics_final),
                    "removed_duplicates": len(duplicates_removed),
                    "removed_specificity": len(invalid_specificity),
                    "removed_invalid_llm": len(invalid_atomics_llm)
                }
            }
        }
        
        new_removed = [r for r in all_invalid if r['source'] == 'current']
        old_removed = [r for r in all_invalid if r['source'] == 'previous']
        
        validation_summary = {
            "direction_1_new_atomics": {
                "total_validated": len([a for a in all_atomics_list if a['source'] == 'current']),
                "kept": new_count,
                "removed": len(new_removed),
                "removed_details": new_removed,
                "kept_ids": [a['atomic']['id'] for a in valid_atomics_final if a['source'] == 'current']
            },
            "direction_2_old_atomics": {
                "total_checked": len([a for a in all_atomics_list if a['source'] == 'previous']),
                "kept": old_count,
                "removed": len(old_removed),
                "removed_details": old_removed,
                "kept_ids": [a['atomic']['id'] for a in valid_atomics_final if a['source'] == 'previous']
            },
            "merged_output": {
                "total_originals": len(all_originals),
                "total_atomics": len(valid_atomics_final),
                "old_atomics": old_count,
                "new_atomics": new_count
            }
        }
        
        return {
            "merged_constraint": merged_constraint,
            "validation_summary": validation_summary
        }