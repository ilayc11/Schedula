"""
Stage 0: Translation and Validation
First stage in pipeline - translates (if needed) then validates user input

Flow:
1. Translation: Detect language and translate to English if needed
2. Validation: Validate the TRANSLATED text (not original)

Returns:
- success=True + processed_input (translated) if valid constraint-related message
- success=False + clarification_message if unclear/invalid input
"""
from typing import Dict, Any

from .base_stage import BaseStage
from ..llm.interface import LLMInterface
from ..language import get_language_translator

class ClarificationStage(BaseStage):
    """
    Stage 0: Translates then validates user input
    
    Process:
    1. Translation: Detects and translates non-English input to English
    2. Validation: Validates the TRANSLATED text for:
       - Constraint-related content (availability, scheduling, time preferences)
       - Clear enough to process
       - Not a question/greeting/unrelated content
    
    Important: Validation always happens AFTER translation, ensuring all
    subsequent pipeline stages work with English text.
    """
    
    def __init__(self, llm: LLMInterface):
        super().__init__(llm, "clarification")
        self.language_translator = get_language_translator()
    
    async def process(self, user_input: str) -> Dict[str, Any]:
        """
        Translate (if needed) then validate user input
        
        Args:
            user_input: Raw text from user (any language)
            
        Returns:
            {
                "success": bool,
                "is_constraint": bool,
                "clarification_needed": bool,
                "clarification_message": str or None,
                "processed_input": str,  # TRANSLATED text for next stages
                "language_metadata": dict,  # Translation info
                "reasoning": str,
                "confidence": float
            }
        
        Note: processed_input is ALWAYS used for subsequent stages, ensuring
        all pipeline stages work with English (translated) text.
        """
        print(f"\n{'='*80}")
        print(f"🔍 STAGE 0: Input Validation & Clarification")
        print(f"{'='*80}")
        print(f"Original input: \"{user_input}\"")
        
        # ═══════════════════════════════════════════════════════════════
        # STEP 1: TRANSLATION (if needed)
        # ═══════════════════════════════════════════════════════════════
        processed_input, language_metadata = self.language_translator.process_text(user_input)
        
        # Show translation info
        if language_metadata.get("was_translated", False):
            print(f"\n🌐 Translation detected:")
            print(f"   Original language: {language_metadata.get('detected_language', 'unknown')}")
            print(f"   Translated text: \"{processed_input}\"")
        else:
            print(f"   No translation needed (language: {language_metadata.get('detected_language', 'English')})")
        
        # ═══════════════════════════════════════════════════════════════
        # STEP 2: VALIDATION (on translated text)
        # ═══════════════════════════════════════════════════════════════
        print(f"\n📋 Validating: \"{processed_input}\"")
        
        # Build prompt (use processed/translated input)
        prompt = f"""USER INPUT:
"{processed_input}"

Validate this input:
1. Is it a scheduling/availability constraint?
2. Is it clear enough to process?
3. Does it need clarification?

Return JSON validation result:"""
        
        # Call LLM
        response = await self.llm.call(prompt, self.system_prompt)
        
        # Parse response using base class method
        try:
            result = self._parse_json(response, default={
                "success": True,
                "is_constraint": True,
                "is_clear": False,
                "clarification_needed": False,
                "clarification_message": None,
                "reasoning": "Parse error - allowing through",
                "confidence": 0.0
            })
            
            success = result.get("success", False)
            clarification_needed = result.get("clarification_needed", False)
            clarification_message = result.get("clarification_message")
            reasoning = result.get("reasoning", "")
            
            print(f"\n{'~'*80}")
            print(f"Validation Result (on translated text):")
            print(f"  Success: {success}")
            print(f"  Is Constraint: {result.get('is_constraint', False)}")
            print(f"  Is Clear: {result.get('is_clear', False)}")
            print(f"  Reasoning: {reasoning}")
            
            if clarification_needed:
                print(f"\n💬 Clarification Needed:")
                print(f"  Message: {clarification_message}")
            else:
                print(f"\n✅ Input valid - proceeding to next stage")
                if language_metadata.get("was_translated", False):
                    print(f"   (Using translated text for all subsequent stages)")
            
            print(f"{'='*80}\n")
            
            return {
                "success": success,
                "is_constraint": result.get("is_constraint", False),
                "is_clear": result.get("is_clear", False),
                "clarification_needed": clarification_needed,
                "clarification_message": clarification_message,
                "processed_input": processed_input,  # Translated text for next stages
                "language_metadata": language_metadata,  # Track translation info
                "reasoning": reasoning,
                "confidence": result.get("confidence", 0.0)
            }
            
        except Exception as e:
            print(f"⚠️  Error: {e}")
            print(f"Raw response: {response[:200]}")
            
            # Safe default: let it through if can't parse
            return {
                "success": True,
                "is_constraint": True,
                "is_clear": False,
                "clarification_needed": False,
                "clarification_message": None,
                "processed_input": processed_input,  # Translated text for next stages
                "language_metadata": language_metadata,
                "reasoning": f"Parse error - allowing through: {str(e)}",
                "confidence": 0.0
            }