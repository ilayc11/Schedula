"""
Stage 2: Classification - Classify constraint polarity and priority
"""
from typing import Dict, Any

from .base_stage import BaseStage
from ..llm.interface import LLMInterface


class ClassificationStage(BaseStage):
    """Stage 2: Classify constraint polarity and type - FIXED VERSION"""
    
    def __init__(self, llm: LLMInterface):
        super().__init__(llm, "classification")
    
    async def process(self, constraint_text: str) -> Dict[str, Any]:
        """Classify constraint with improved priority detection"""
        print(f"\n{'='*80}")
        print(f"🔹 STAGE 2: CLASSIFICATION (FIXED)")
        print(f"{'='*80}")
        print(f"Constraint: \"{constraint_text}\"")
        
        prompt = f"""Constraint: "{constraint_text}"

Classify (remember: 'only' = HARD priority!):"""
        
        print(f"⏳ Calling LLM for classification...")
        response = await self.llm.call(prompt, self.system_prompt)
        
        try:
            result = self._parse_json(response, default={
                "polarity": "NEGATIVE",
                "type": "BLOCK",
                "priority": "hard",
                "confidence": 0.3,
                "reasoning": "Parsing failed - defaulted to HARD"
            })
            
            # SAFETY CHECK: If text contains "only" or "cannot", force HARD priority
            lower_text = constraint_text.lower()
            if any(keyword in lower_text for keyword in ['only', 'cannot', "can't", 'unavailable', 'not available', 'busy']):
                if result.get('priority') == 'soft':
                    print(f"⚠️  WARNING: Overriding soft→hard (detected absolute restriction keyword)")
                result['priority'] = 'hard'
            
            print(f"✅ Classification complete:")
            print(f"   Polarity: {result.get('polarity', 'UNKNOWN')}")
            print(f"   Type: {result.get('type', 'UNKNOWN')}")
            print(f"   Priority: {result.get('priority', 'UNKNOWN')}")
            print(f"   Confidence: {result.get('confidence', 0):.2f}")
            print(f"   Reasoning: {result.get('reasoning', 'N/A')}")
            
            return result
        except Exception as e:
            print(f"❌ Error: {e}")
            # Default to HARD for safety
            return {
                "polarity": "NEGATIVE",
                "type": "BLOCK",
                "priority": "hard",
                "confidence": 0.3,
                "reasoning": "Parsing failed - defaulted to HARD"
            }

