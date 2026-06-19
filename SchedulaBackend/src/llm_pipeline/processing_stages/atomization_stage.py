"""
Stage 1: Atomization - Split compound constraints into atomic units
"""
from typing import List, Dict, Any

from .base_stage import BaseStage
from ..llm.interface import LLMInterface


class AtomizationStage(BaseStage):
    """
    Stage 1: Smart atomization - recognizes single vs compound constraints
    
    IMPROVED: "I can work Monday morning" = 1 constraint (NOT split!)
    """
    
    def __init__(self, llm: LLMInterface):
        super().__init__(llm, "atomization")
    
    async def process(self, input_text: str) -> List[Dict[str, Any]]:
        """Split input into atomic constraints (smarter logic)"""
        print(f"\n{'='*80}")
        print(f"🔹 STAGE 1: ATOMIZATION")
        print(f"{'='*80}")
        print(f"Input: \"{input_text}\"")
        
        prompt = f"""Input constraint text:
"{input_text}"

Atomize into constraints (remember: day+time = single constraint!):"""
        
        print(f"⏳ Calling LLM for atomization...")
        response = await self.llm.call(prompt, self.system_prompt)
        
        try:
            result = self._parse_json(response, default={"atomic_constraints": [{"text": input_text, "confidence": 0.5}]})
            atomic_constraints = result.get("atomic_constraints", [{"text": input_text, "confidence": 0.5}])
            
            print(f"✅ Atomization complete: {len(atomic_constraints)} atomic constraint(s)")
            for idx, ac in enumerate(atomic_constraints):
                print(f"   [{idx+1}] \"{ac.get('text')}\" (confidence: {ac.get('confidence', 0):.2f})")
            
            return atomic_constraints
        except Exception as e:
            print(f"❌ Error: {e}")
            print(f"Raw response: {response[:200]}")
            return [{"text": input_text, "confidence": 0.5}]

