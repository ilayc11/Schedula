"""
Text Combination Stage - Linguistically merge multiple constraint texts

This stage takes multiple natural language constraint statements and combines them
into a single coherent statement using LLM-based linguistic merging.
"""
import json
from typing import List, Dict, Any

from .base_stage import BaseStage


class TextCombinationStage(BaseStage):
    """
    Combines multiple constraint texts into a single natural language statement.
    
    Used when a user has existing constraints and enters a new one that may conflict.
    Instead of merging at the atomic level, we merge the raw texts linguistically,
    then re-process the combined text through the full pipeline.
    """
    
    def __init__(self, llm):
        super().__init__(llm, "text_combination")
    
    async def process(self, constraint_texts: List[str]) -> Dict[str, Any]:
        """
        Combine multiple constraint texts into one coherent statement.
        
        Args:
            constraint_texts: List of constraint texts in chronological order
                             (oldest first, newest last)
        
        Returns:
            Dict with:
                - combined_text: The merged constraint text
                - original_count: Number of original texts
                - success: Whether the combination succeeded
        """
        print(f"\n{'='*80}")
        print(f"🔤 TEXT COMBINATION STAGE")
        print(f"{'='*80}")
        print(f"Combining {len(constraint_texts)} constraint texts...")
        
        # Handle edge cases
        if not constraint_texts:
            return {
                "combined_text": "",
                "original_count": 0,
                "success": False,
                "error": "No texts provided"
            }
        
        if len(constraint_texts) == 1:
            print(f"  ℹ️  Only one text, no combination needed")
            return {
                "combined_text": constraint_texts[0],
                "original_count": 1,
                "success": True
            }
        
        # Print all input texts
        print(f"\n📝 Input texts (oldest → newest):")
        for i, text in enumerate(constraint_texts, 1):
            print(f"  {i}. \"{text}\"")
        
        # Prepare input for LLM
        texts_with_order = [
            {"text": text, "order": i}
            for i, text in enumerate(constraint_texts, 1)
        ]
        
        prompt = f"""Combine the following constraint statements into a single coherent natural language statement:

{json.dumps(texts_with_order, indent=2)}

Remember:
- Resolve conflicts by preferring newer, more specific statements
- Use natural, grammatically correct language
- Preserve all time specificity
- Output ONLY the combined text, nothing else (no JSON, no explanations)
"""
        
        try:
            # Call LLM
            print(f"\n⏳ Calling LLM to combine texts...")
            combined_text = await self.llm.call(prompt, self.system_prompt)
            
            # Clean up response (remove any JSON formatting if present)
            combined_text = combined_text.strip()
            # Remove quotes if LLM wrapped the response in them
            if combined_text.startswith('"') and combined_text.endswith('"'):
                combined_text = combined_text[1:-1]
            if combined_text.startswith("'") and combined_text.endswith("'"):
                combined_text = combined_text[1:-1]
            
            print(f"\n✅ Combined text:")
            print(f"   \"{combined_text}\"")
            
            return {
                "combined_text": combined_text,
                "original_count": len(constraint_texts),
                "original_texts": constraint_texts,
                "success": True
            }
            
        except Exception as e:
            print(f"\n❌ Error combining texts: {e}")
            # Fallback: join with "and"
            fallback_text = " and ".join(constraint_texts)
            print(f"   Using fallback: \"{fallback_text}\"")
            
            return {
                "combined_text": fallback_text,
                "original_count": len(constraint_texts),
                "original_texts": constraint_texts,
                "success": False,
                "error": str(e),
                "used_fallback": True
            }

