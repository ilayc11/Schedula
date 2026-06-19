"""
Stage 3.5: Conflict Handler - ENHANCED WITH TRUTH TABLE
Forces correct interpretation of formula results
"""
import json
from typing import List, Dict, Any
import re

from .base_stage import BaseStage
from ..llm.interface import LLMInterface


class ConflictHandlerStage(BaseStage):
    """Validates negated constraints against combined original constraints."""
    
    def __init__(self, llm: LLMInterface, batch_size: int = 2):
        super().__init__(llm, "conflict_validation")
        self.batch_size = batch_size
    
    def _format_originals_for_prompt(self, originals: List[str]) -> str:
        """Format original constraints for LLM prompt"""
        formatted = []
        for idx, original in enumerate(originals, 1):
            formatted.append(f"  {idx}. \"{original}\"")
        return "\n".join(formatted)
    
    def _format_negated_batch_for_prompt(self, negated_batch: List[Dict[str, Any]]) -> str:
        """Format a batch of negated constraints for LLM prompt"""
        formatted = []
        for idx, neg in enumerate(negated_batch, 1):
            text = neg.get("text", "")
            priority = neg.get("priority", "hard")
            formatted.append(f"  {idx}. \"{text}\" (priority: {priority})")
        return "\n".join(formatted)
    
    def _normalize_llm_response(self, data: Any, negated_batch: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Normalize LLM response to expected format."""
        if isinstance(data, list):
            validations_list = data
        elif isinstance(data, dict) and "validations" in data:
            validations_list = data["validations"]
        else:
            return None
        
        normalized_validations = []
        for idx, item in enumerate(validations_list):
            if not isinstance(item, dict):
                continue
            
            normalized = {
                "negated_constraint": (
                    item.get("negated_constraint") or 
                    item.get("constraint") or 
                    item.get("text") or
                    negated_batch[idx].get("text", "") if idx < len(negated_batch) else ""
                ),
                "is_valid": (
                    item.get("is_valid") if "is_valid" in item
                    else not item.get("contradiction", False) if "contradiction" in item
                    else item.get("action", "keep") == "keep"
                ),
                "reasoning": item.get("reasoning", "No reasoning provided"),
                "action": (
                    item.get("action") if "action" in item
                    else item.get("decision") if "decision" in item
                    else ("keep" if item.get("is_valid", True) else "remove")
                ),
                "contradicts_originals": item.get("contradicts_originals", [])
            }
            
            normalized_validations.append(normalized)
        
        return {"validations": normalized_validations}
    
    def _robust_json_parse(self, response: str, negated_batch: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Robust JSON parser that handles multiple common LLM malformations."""
        strategies = [
            ("Direct parse", lambda r: json.loads(r)),
            ("Strip markdown", lambda r: json.loads(r.strip('`').strip())),
            ("Remove json prefix", lambda r: json.loads(re.sub(r'^```json\s*', '', r, flags=re.IGNORECASE).strip('`').strip())),
            ("Remove code fences", lambda r: json.loads(re.sub(r'```[a-z]*\s*', '', r).replace('```', '').strip())),
            ("Extract first array", lambda r: json.loads(re.search(r'\[[\s\S]*\]', r).group(0))),
            ("Extract first object", lambda r: json.loads(re.search(r'\{[\s\S]*\}', r).group(0))),
            ("Extract complete array", lambda r: json.loads(re.search(r'\[(?:[^\[\]]|(?:\[[^\[\]]*\]))*\]', r, re.DOTALL).group(0))),
            ("Extract complete object", lambda r: json.loads(re.search(r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}', r, re.DOTALL).group(0))),
            ("Fix trailing commas", lambda r: json.loads(re.sub(r',(\s*[}\]])', r'\1', r))),
            ("Extract between {} markers", lambda r: json.loads('{' + r.split('{', 1)[1].rsplit('}', 1)[0] + '}')),
            ("Extract between [] markers", lambda r: json.loads('[' + r.split('[', 1)[1].rsplit(']', 1)[0] + ']')),
            ("Strip before [ or {", lambda r: json.loads(re.sub(r'^[^\[\{]*', '', r))),
        ]
        
        for strategy_name, strategy_func in strategies:
            try:
                result = strategy_func(response)
                normalized = self._normalize_llm_response(result, negated_batch)
                
                if not normalized:
                    continue
                if not isinstance(normalized, dict):
                    continue
                if "validations" not in normalized:
                    continue
                if not isinstance(normalized["validations"], list):
                    continue
                
                print(f"   ✅ JSON parsed using strategy: {strategy_name}")
                return normalized
                
            except (json.JSONDecodeError, AttributeError, IndexError, TypeError, KeyError):
                continue
        
        print(f"❌ All JSON parsing strategies failed")
        print(f"   Raw response (first 500 chars):")
        print(f"   {response[:500]}...")
        print(f"   Falling back to 'keep all' default")
        
        return {
            "validations": [
                {
                    "negated_constraint": neg.get("text", ""),
                    "is_valid": True,
                    "reasoning": "JSON parsing failed - kept by default for safety",
                    "action": "keep",
                    "contradicts_originals": []
                }
                for neg in negated_batch
            ]
        }
    
    async def _validate_batch(
        self,
        originals: List[str],
        negated_batch: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Validate a batch of negated constraints against originals."""
        
        prompt = f"""ORIGINAL CONSTRAINTS (what IS available):
{self._format_originals_for_prompt(originals)}

NEGATED CONSTRAINTS TO VALIDATE:
{self._format_negated_batch_for_prompt(negated_batch)}

For EACH constraint:
1. Saturday? → remove immediately
2. Entire day block? → check if day in originals
3. Time constraint? → Apply formula, check BOTH conditions, use truth table

Remember: ONLY ✓✓ = overlap! Any ✗ = NO overlap!

Return JSON array with {len(negated_batch)} results. Use mandatory reasoning format for time constraints."""

        response = await self.llm.call(prompt, self.system_prompt)
        parsed_result = self._robust_json_parse(response, negated_batch)
        return parsed_result
    
    async def process(
        self,
        original_constraints: List[str],
        negated_constraints: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Validate negated constraints against combined original constraints."""
        print(f"\n{'='*80}")
        print(f"🔍 STAGE 3.5: CONFLICT HANDLER")
        print(f"{'='*80}")
        print(f"Original constraints count: {len(original_constraints)}")
        print(f"Negated constraints to validate: {len(negated_constraints)}")
        print(f"Batch size: {self.batch_size}")
        print(f"\nOriginal constraints:")
        for idx, orig in enumerate(original_constraints, 1):
            print(f"  {idx}. \"{orig}\"")
        
        if not negated_constraints:
            print(f"⚠️  No negated constraints to validate")
            return {
                "valid_constraints": [],
                "removed_constraints": [],
                "validation_log": []
            }
        
        valid_constraints = []
        removed_constraints = []
        validation_log = []
        
        total_batches = (len(negated_constraints) + self.batch_size - 1) // self.batch_size
        
        for batch_idx in range(0, len(negated_constraints), self.batch_size):
            batch_num = (batch_idx // self.batch_size) + 1
            negated_batch = negated_constraints[batch_idx:batch_idx + self.batch_size]
            
            print(f"\n{'~'*80}")
            print(f"Processing Batch {batch_num}/{total_batches} ({len(negated_batch)} constraints)")
            print(f"{'~'*80}")
            
            for idx, neg in enumerate(negated_batch):
                print(f"  [{batch_idx + idx + 1}] \"{neg.get('text', '')}\" (priority: {neg.get('priority', 'hard')})")
            
            print(f"⏳ Calling LLM for validation...")
            
            validation_result = await self._validate_batch(original_constraints, negated_batch)
            validations = validation_result.get("validations", [])
            
            for idx, (negated, validation) in enumerate(zip(negated_batch, validations)):
                constraint_num = batch_idx + idx + 1
                text = negated.get("text", "")
                is_valid = validation.get("is_valid", True)
                reasoning = validation.get("reasoning", "No reasoning provided")
                action = validation.get("action", "keep")
                contradicts = validation.get("contradicts_originals", [])
                
                log_entry = {
                    "constraint_number": constraint_num,
                    "text": text,
                    "is_valid": is_valid,
                    "reasoning": reasoning,
                    "action": action,
                    "contradicts_originals": contradicts
                }
                validation_log.append(log_entry)
                
                if is_valid and action == "keep":
                    valid_constraints.append(negated)
                    print(f"\n  ✅ [{constraint_num}] KEEP: \"{text}\"")
                    print(f"     Reasoning: {reasoning}")
                else:
                    removed_constraints.append(negated)
                    print(f"\n  ❌ [{constraint_num}] REMOVE: \"{text}\"")
                    print(f"     Reasoning: {reasoning}")
                    if contradicts:
                        print(f"     Contradicts original(s): {contradicts}")
        
        print(f"\n{'='*80}")
        print(f"✅ CONFLICT HANDLER COMPLETE")
        print(f"{'='*80}")
        print(f"Total validated: {len(negated_constraints)}")
        print(f"Valid (kept): {len(valid_constraints)}")
        print(f"Invalid (removed): {len(removed_constraints)}")
        print(f"Removal rate: {len(removed_constraints) / len(negated_constraints) * 100:.1f}%")
        
        if removed_constraints:
            print(f"\n📋 Removed constraints summary:")
            for idx, removed in enumerate(removed_constraints, 1):
                log = next((l for l in validation_log if l["text"] == removed.get("text")), {})
                print(f"  {idx}. \"{removed.get('text', '')}\"")
                print(f"     → {log.get('reasoning', 'N/A')}")
        
        return {
            "valid_constraints": valid_constraints,
            "removed_constraints": removed_constraints,
            "validation_log": validation_log
        }