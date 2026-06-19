"""
Stage 3: Negation - ULTRA-CLEAR VERSION
Fix: Emphasize NOT blocking the available time/day mentioned in input
"""
from typing import Dict, Any

from .base_stage import BaseStage
from ..llm.interface import LLMInterface


class NegationStage(BaseStage):
    """Stage 3: Convert positive constraints to negative blocks - ULTRA-CLEAR"""
    
    def __init__(self, llm: LLMInterface):
        super().__init__(llm, "negation")
    
    async def process(self, constraint_text: str, priority: str) -> Dict[str, Any]:
        """Convert positive to negative with validation - ULTRA-CLEAR"""
        print(f"\n{'='*80}")
        print(f"🔹 STAGE 3: NEGATION (ULTRA-CLEAR)")
        print(f"{'='*80}")
        print(f"Positive constraint: \"{constraint_text}\"")
        print(f"Input priority: {priority}")
        
        prompt = f"""Convert this positive constraint to negative blocks:

Constraint: "{constraint_text}"
Priority: {priority}

CRITICAL: Identify what IS available, then block everything that is NOT available.
DO NOT block the available time/day itself!
ALL output blocks must have priority = {priority}"""
        
        print(f"⏳ Calling LLM for negation...")
        response = await self.llm.call(prompt, self.system_prompt)
        
        try:
            result = self._parse_json(response, default={
                "inverted_constraints": [],
                "inversion_summary": "Failed to parse LLM response"
            })
            
            inverted = result.get("inverted_constraints", [])
            
            # Deduplicate and force correct priority
            deduplicated = []
            seen_texts = set()
            
            for constraint in inverted:
                text = constraint.get("text", "")
                
                if text in seen_texts:
                    print(f"⚠️  Skipping duplicate: \"{text}\"")
                    continue
                
                seen_texts.add(text)
                constraint["priority"] = priority  # Force correct priority
                deduplicated.append(constraint)
            
            result["inverted_constraints"] = deduplicated
            
            print(f"✅ Negation complete: {len(deduplicated)} unique inverted constraint(s)")
            print(f"   Summary: {result.get('inversion_summary', 'N/A')}")
            print(f"   All constraints have priority: {priority}")
            
            for idx, inv in enumerate(deduplicated):
                print(f"   [{idx+1}] \"{inv.get('text')}\" (priority: {inv.get('priority')}, conf: {inv.get('confidence', 0):.2f})")
            
            return result
            
        except Exception as e:
            print(f"❌ Error: {e}")
            print(f"   Raw response: {response[:200]}...")
            return {
                "inverted_constraints": [],
                "inversion_summary": f"Failed to parse LLM response: {str(e)}"
            }