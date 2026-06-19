"""
Constraint Processing Pipeline - SIMPLIFIED VERSION

Clear linear flow:
0. Translation → Validation (on translated text)
0.5. Text Combination (if merging with existing constraints - AFTER translation)
1. Atomize → Classify → Negate → Deduplicate → Validate → Extract

IMPORTANT: Translation happens FIRST, then all processing (including validation 
and text merging) happens on the English translated text.
"""

from typing import Dict, Any, List, Optional, Callable, Awaitable

from ..llm.interface import LLMInterface
from ..models.enums import ConstraintType
from ..models.atomic_constraint import AtomicConstraint
from ..models.processing_result import ProcessingResult
from ..validators.rule_validator import RuleBasedValidator
from ..validators.deduplicator import ConstraintDeduplicator
from ..validators.conflict_detector import ConflictDetector
from ..output.csp_logger import CSPOutputLogger
from ..processing_stages.atomization_stage import AtomizationStage
from ..processing_stages.classification_stage import ClassificationStage
from ..processing_stages.negation_stage import NegationStage
from ..processing_stages.conflict_handler_stage import ConflictHandlerStage
from ..processing_stages.extraction_stage import ExtractionStage
from ..models.time_slot import TimeSlot
from ..processing_stages.stage_0_clarification import ClarificationStage
from ..processing_stages.wrap_conflict_handler_stage import WrapConflictHandlerStage
from ..processing_stages.text_combination_stage import TextCombinationStage


class ConstraintProcessingPipeline:
    """
    Orchestrates the full constraint processing pipeline.
    
    COMPLETE FLOW:
    0. Translation & Validation:
       - Translate input to English (if needed)
       - Validate the TRANSLATED text (not original)
    0.5. Text Combination (optional):
       - If merging with existing constraints, combine AFTER translation
       - All text merging happens in English
    1. Atomization: Split compound constraints
    2. Classification: Determine polarity and priority
    3. Negation: Convert POSITIVE → NEGATIVE constraints (collect all)
    4. Deduplication: Remove duplicate negated constraints (before validation)
    5. Conflict Handler: Validate negated constraints (if multiple originals)
    6. Extraction: Extract days/times ONLY from valid constraints
    7. Validation: Rule-based checks
    8. Conflict Detection: Final sanity check
    9. Deduplication: Remove any remaining duplicates
    10. Logging: Write to CSP output
    
    CRITICAL: Translation happens FIRST. All subsequent stages work with English text.
    """
    
    def __init__(self, llm: LLMInterface, csp_logger: CSPOutputLogger, conflict_handler_batch_size: int = 3):
        self.atomization = AtomizationStage(llm)
        self.classification = ClassificationStage(llm)
        self.negation = NegationStage(llm)
        self.conflict_handler = ConflictHandlerStage(llm, batch_size=conflict_handler_batch_size)
        self.extraction = ExtractionStage(llm)
        self.validator = RuleBasedValidator()
        self.conflict_detector = ConflictDetector()
        self.deduplicator = ConstraintDeduplicator()
        self.csp_logger = csp_logger
        self.stage0 = ClarificationStage(llm)
        self.wrap_stage = WrapConflictHandlerStage(llm)
        self.text_combination_stage = TextCombinationStage(llm)
        self.llm = llm  # Store LLM reference for access by other components
    def _build_metadata(
        self,
        original_polarity: str,
        extraction_confidence: float,
        reasoning: Optional[str] = None,
        inversion_summary: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build standardized metadata structure for constraints"""
        metadata = {
            "original_polarity": original_polarity,
            "extraction_confidence": extraction_confidence,
        }
        if reasoning:
            metadata["reasoning"] = reasoning
        if inversion_summary:
            metadata["inversion_summary"] = inversion_summary
        return metadata
    
    def _create_atomic_constraint(
        self,
        constraint_id: str,
        text: str,
        priority: str,
        extraction: Dict[str, Any],
        confidence: float,
        metadata: Dict[str, Any]
    ) -> AtomicConstraint:
        """Create AtomicConstraint from extraction result"""
        
        # Determine constraint type based on priority
        constraint_type = ConstraintType.PREFERENCE if priority == "soft" else ConstraintType.BLOCK
        
        return AtomicConstraint(
            constraint_id=constraint_id,
            constraint_type=constraint_type,
            days=extraction["days"],
            time_slot=extraction.get("time_slot"),  # Always a TimeSlot object (full-day blocks use full working hours)
            priority=priority,
            original_text=text,
            confidence_score=confidence,
            metadata=metadata
        )
    
    def _deduplicate_negated_constraints(self, negated_constraints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Deduplicate negated constraints by text, keeping highest confidence version.
        This saves unnecessary LLM calls in conflict validation.
        """
        seen_texts = {}
        unique_constraints = []
        
        for constraint in negated_constraints:
            text = constraint.get("text", "")
            confidence = constraint.get("confidence", 0.0)
            
            if text not in seen_texts:
                # First occurrence - keep it
                seen_texts[text] = constraint
                unique_constraints.append(constraint)
            else:
                # Duplicate found - keep higher confidence version
                existing_confidence = seen_texts[text].get("confidence", 0.0)
                if confidence > existing_confidence:
                    # Replace with higher confidence version
                    idx = unique_constraints.index(seen_texts[text])
                    unique_constraints[idx] = constraint
                    seen_texts[text] = constraint
        
        return unique_constraints
    
    async def process(
        self,
        input_text: str,
        existing_constraint_texts: Optional[List[str]] = None,
        on_stage_update: Optional[Callable[[str], Awaitable[None]]] = None
    ) -> ProcessingResult:
        """
        Process natural language constraint
        
        Args:
            input_text: New constraint text from user
            existing_constraint_texts: Optional list of existing constraint texts to merge with
                                      (will be combined AFTER translation)
            on_stage_update: Optional async callback for progress updates.
                            Called with stage name before each processing stage.
        """
        print(f"\n{'#'*80}")
        print(f"# STARTING CONSTRAINT PROCESSING PIPELINE (SIMPLIFIED)")
        print(f"# Input: \"{input_text}\"")
        if existing_constraint_texts:
            print(f"# Existing constraints to merge: {len(existing_constraint_texts)}")
        print(f"{'#'*80}\n")
        

        # ═══════════════════════════════════════════════════════════════
        # STAGE 0: TRANSLATION → VALIDATION
        # Step 1: Translate input to English (if needed)
        # Step 2: Validate the TRANSLATED text (not original)
        # ═══════════════════════════════════════════════════════════════
        if on_stage_update:
            await on_stage_update("stage_0")
        
        validation = await self.stage0.process(input_text)
    
        if not validation["success"]:
            # We must return a ProcessingResult object, not a dict
            return ProcessingResult(
                success=False,
                atomic_constraints=[],
                original_input=input_text,
                processing_metadata={
                    "total_atomic_constraints": 0,
                    "valid_constraints": 0,
                    "needs_clarification": True,
                    "clarification_message": validation["clarification_message"]
                },
                errors=[], 
                warnings=[f"Clarification needed: {validation['clarification_message']}"]
            )

        # Use the processed (TRANSLATED and VALIDATED) input from Stage 0
        # ALL subsequent stages work with this English text
        processed_input = validation["processed_input"]
        
        # ═══════════════════════════════════════════════════════════════
        # STAGE 0.5: TEXT COMBINATION (AFTER TRANSLATION & VALIDATION)
        # ═══════════════════════════════════════════════════════════════
        # If there are existing constraints to merge, combine them NOW
        # This ensures all text merging happens in English (after translation)
        if existing_constraint_texts:
            if on_stage_update:
                await on_stage_update("text_combination")
            
            print(f"\n{'='*80}")
            print(f"🔤 TEXT COMBINATION (AFTER TRANSLATION)")
            print(f"{'='*80}")
            
            # Combine existing constraints with the new (translated) input
            # Order: existing constraints first, then new input last
            all_texts = existing_constraint_texts + [processed_input]
            
            combination_result = await self.text_combination_stage.process(all_texts)
            
            if combination_result["success"]:
                processed_input = combination_result["combined_text"]
                print(f"✅ Successfully combined {len(all_texts)} constraint texts")
                print(f"   Result: \"{processed_input}\"")
            else:
                print(f"⚠️  Text combination failed, using fallback")
                processed_input = combination_result["combined_text"]  # Fallback still returns combined text

        errors = []
        warnings = []
        atomic_constraints = []
        
        # Initialize variables that may be used in summary (to avoid unbound warnings)
        unique_negated: List[Dict[str, Any]] = []
        valid_negated: List[Dict[str, Any]] = []
        
        try:
            # ═══════════════════════════════════════════════════════════════
            # STAGE 1: ATOMIZATION
            # ═══════════════════════════════════════════════════════════════
            if on_stage_update:
                await on_stage_update("atomization")
            
            atomic_texts = await self.atomization.process(processed_input)
            
            print(f"\n{'='*80}")
            print(f"📋 PROCESSING {len(atomic_texts)} ATOMIC CONSTRAINT(S)")
            print(f"{'='*80}")
            
            # Collect all negated constraints and direct negatives
            all_negated_constraints = []
            original_texts = []
            
            # ═══════════════════════════════════════════════════════════════
            # STAGE 2 & 3: CLASSIFY AND NEGATE (for POSITIVE constraints)
            # ═══════════════════════════════════════════════════════════════
            if on_stage_update:
                await on_stage_update("classification")
            
            for idx, atomic_data in enumerate(atomic_texts):
                constraint_text = atomic_data.get("text", "")
                atomization_confidence = atomic_data.get("confidence", 0.5)
                
                print(f"\n{'~'*80}")
                print(f"🔄 Processing Atomic Constraint #{idx + 1}: \"{constraint_text}\"")
                print(f"{'~'*80}")
                
                try:
                    # Classify
                    classification = await self.classification.process(constraint_text)
                    polarity = classification.get("polarity", "NEGATIVE")
                    priority = classification.get("priority", "hard")
                    
                    if polarity == "POSITIVE":
                        print(f"➡️  POSITIVE constraint → Will negate")
                        original_texts.append(constraint_text)
                        
                        # Negate
                        negation_result = await self.negation.process(constraint_text, priority)
                        inverted_constraints = negation_result.get("inverted_constraints", [])
                        
                        # Add to collection with metadata
                        for inv_constraint in inverted_constraints:
                            inv_constraint["source_atomic_idx"] = idx
                            inv_constraint["atomization_confidence"] = atomization_confidence
                            inv_constraint["inversion_summary"] = negation_result.get("inversion_summary", "")
                        
                        all_negated_constraints.extend(inverted_constraints)
                        print(f"   ✅ Negated to {len(inverted_constraints)} constraint(s)")
                    
                    else:
                        print(f"➡️  NEGATIVE constraint → Direct extraction")
                        
                        # Direct extraction for NEGATIVE constraints
                        extraction = await self.extraction.process(constraint_text)
                        extraction["priority"] = priority
                        
                        # Validate
                        validation = self.validator.validate(extraction)
                        
                        if validation["is_valid"]:
                            constraint = self._create_atomic_constraint(
                                constraint_id=f"constraint_{idx}",
                                text=constraint_text,
                                priority=priority,
                                extraction=extraction,
                                confidence=min(atomization_confidence, classification.get("confidence", 0.8), extraction.get("confidence", 0.8)),
                                metadata=self._build_metadata(
                                    original_polarity="NEGATIVE",
                                    extraction_confidence=extraction.get("confidence", 0.8),
                                    reasoning=classification.get("reasoning", "")
                                )
                            )
                            atomic_constraints.append(constraint)
                            print(f"   ✅ Constraint created: constraint_{idx}")
                        else:
                            warning_msg = f"Validation failed: {', '.join(validation['issues'])}"
                            warnings.append(warning_msg)
                            print(f"   ⚠️  {warning_msg}")
                
                except Exception as e:
                    error_msg = f"Error processing '{constraint_text}': {str(e)}"
                    errors.append(error_msg)
                    print(f"   ❌ {error_msg}")
            
            # ═══════════════════════════════════════════════════════════════
            # STAGE 4: DEDUPLICATE NEGATED CONSTRAINTS
            # ═══════════════════════════════════════════════════════════════
            if all_negated_constraints:
                if on_stage_update:
                    await on_stage_update("deduplication")
                
                print(f"\n{'='*80}")
                print(f"🔍 DEDUPLICATION (BEFORE VALIDATION)")
                print(f"{'='*80}")
                print(f"Total negated constraints: {len(all_negated_constraints)}")
                
                unique_negated = self._deduplicate_negated_constraints(all_negated_constraints)
                duplicates_removed = len(all_negated_constraints) - len(unique_negated)
                
                print(f"Unique constraints: {len(unique_negated)}")
                print(f"Duplicates removed: {duplicates_removed}")
                if duplicates_removed > 0:
                    print(f"Reduction: {duplicates_removed / len(all_negated_constraints) * 100:.1f}%")
                
                # ═══════════════════════════════════════════════════════════════
                # STAGE 5: CONFLICT HANDLER VALIDATION
                # ═══════════════════════════════════════════════════════════════
                if len(original_texts) > 1:
                    if on_stage_update:
                        await on_stage_update("conflict_handler")
                    
                    print(f"\n{'='*80}")
                    print(f"🔍 CONFLICT HANDLER VALIDATION")
                    print(f"{'='*80}")
                    print(f"Validating {len(unique_negated)} constraints against {len(original_texts)} originals")
                    
                    conflict_result = await self.conflict_handler.process(
                        original_constraints=original_texts,
                        negated_constraints=unique_negated
                    )
                    
                    valid_negated = conflict_result["valid_constraints"]
                    removed_negated = conflict_result["removed_constraints"]
                    
                    print(f"\n✅ Validation complete:")
                    print(f"   Valid: {len(valid_negated)}")
                    print(f"   Removed: {len(removed_negated)}")
                else:
                    print(f"\n{'='*80}")
                    print(f"⚡ SKIPPING CONFLICT HANDLER (Single original)")
                    print(f"{'='*80}")
                    valid_negated = unique_negated
                
                # ═══════════════════════════════════════════════════════════════
                # STAGE 6: EXTRACTION (ONLY for valid constraints)
                # ═══════════════════════════════════════════════════════════════
                if on_stage_update:
                    await on_stage_update("extraction")
                
                print(f"\n{'='*80}")
                print(f"📊 EXTRACTING DAYS/TIMES (ONLY for {len(valid_negated)} valid constraints)")
                print(f"{'='*80}")
                
                for idx, inv_constraint in enumerate(valid_negated):
                    inv_text = inv_constraint.get("text", "")
                    inv_priority = inv_constraint.get("priority", "hard")
                    inv_confidence = inv_constraint.get("confidence", 0.8)
                    source_idx = inv_constraint.get("source_atomic_idx", 0)
                    atomization_confidence = inv_constraint.get("atomization_confidence", 0.5)
                    inversion_summary = inv_constraint.get("inversion_summary", "")
                    
                    print(f"\n{'·'*80}")
                    print(f"🔄 Processing Valid Constraint #{idx + 1}: \"{inv_text}\"")
                    print(f"{'·'*80}")
                    
                    try:
                        # Extract
                        extraction = await self.extraction.process(inv_text)
                        extraction["priority"] = inv_priority
                        
                        # Validate
                        validation = self.validator.validate(extraction)
                        
                        if validation["is_valid"]:
                            constraint = self._create_atomic_constraint(
                                constraint_id=f"constraint_{source_idx}_{idx}",
                                text=inv_text,
                                priority=inv_priority,
                                extraction=extraction,
                                confidence=min(atomization_confidence, inv_confidence, extraction.get("confidence", 0.8)),
                                metadata=self._build_metadata(
                                    original_polarity="POSITIVE",
                                    extraction_confidence=extraction.get("confidence", 0.8),
                                    inversion_summary=inversion_summary
                                )
                            )
                            atomic_constraints.append(constraint)
                            print(f"   ✅ Constraint created: constraint_{source_idx}_{idx}")
                        else:
                            warning_msg = f"Validation failed: {', '.join(validation['issues'])}"
                            warnings.append(warning_msg)
                            print(f"   ⚠️  {warning_msg}")
                    
                    except Exception as e:
                        error_msg = f"Error processing '{inv_text}': {str(e)}"
                        errors.append(error_msg)
                        print(f"   ❌ {error_msg}")
            
            # ═══════════════════════════════════════════════════════════════
            # STAGE 7: FINAL CONFLICT DETECTION
            # ═══════════════════════════════════════════════════════════════
            if on_stage_update:
                await on_stage_update("conflict_detection")
            
            print(f"\n{'='*80}")
            print(f"⚠️  FINAL CONFLICT DETECTION")
            print(f"{'='*80}")
            
            conflict_result = self.conflict_detector.detect_conflicts(atomic_constraints)
            
            if conflict_result["has_conflicts"]:
                print(f"Found {len(conflict_result['conflicts'])} potential conflicts:")
                for conflict in conflict_result["conflicts"]:
                    print(f"  - {conflict['type']}: {conflict['description']}")
                    warnings.append(f"Conflict detected: {conflict['description']}")
            else:
                print(f"✅ No conflicts detected")
            
            if conflict_result["warnings"]:
                for warning in conflict_result["warnings"]:
                    print(f"⚠️  {warning}")
                    warnings.append(warning)
            
            # ═══════════════════════════════════════════════════════════════
            # STAGE 8: FINAL DEDUPLICATION
            # ═══════════════════════════════════════════════════════════════
            if on_stage_update:
                await on_stage_update("final_deduplication")
            
            print(f"\n{'='*80}")
            print(f"🔍 FINAL DEDUPLICATION")
            print(f"{'='*80}")
            print(f"Before: {len(atomic_constraints)} constraints")
            
            # Log all constraints before deduplication
            print(f"\n📋 All constraints before deduplication:")
            for idx, c in enumerate(atomic_constraints, 1):
                print(f"  [{idx}] {c.constraint_id}: days={c.days}, time_slot={c.time_slot}, priority={c.priority}")
                print(f"      text: \"{c.original_text[:80]}...\"" if len(c.original_text) > 80 else f"      text: \"{c.original_text}\"")
            
            # Get detailed duplicate report for debugging
            duplicate_report = self.deduplicator.get_duplicate_report(atomic_constraints)
            
            unique_constraints = self.deduplicator.deduplicate(atomic_constraints)
            
            print(f"After: {len(unique_constraints)} constraints")
            print(f"Removed: {len(atomic_constraints) - len(unique_constraints)} duplicates")
            
            # Log duplicate details for debugging
            if duplicate_report["duplicate_groups"]:
                print(f"\n📋 Duplicate Details:")
                for group in duplicate_report["duplicate_groups"]:
                    print(f"  Group: {group['count']} constraints with key {group['key']}")
                    print(f"    IDs: {group['constraint_ids']}")
                    # Show details of duplicates
                    for c in atomic_constraints:
                        if c.constraint_id in group['constraint_ids']:
                            print(f"      - {c.constraint_id}: days={c.days}, time_slot={c.time_slot}, priority={c.priority}, text=\"{c.original_text[:50]}...\"")
            
            # ═══════════════════════════════════════════════════════════════
            # STAGE 9: LOGGING
            # ═══════════════════════════════════════════════════════════════
            if on_stage_update:
                await on_stage_update("logging")
            
            print(f"\n{'='*80}")
            print(f"📝 LOGGING TO CSP OUTPUT")
            print(f"{'='*80}")
            
            for constraint in unique_constraints:
                self.csp_logger.log_constraint(constraint, input_text)
                print(f"✅ Logged: {constraint.constraint_id}")
            
            # ═══════════════════════════════════════════════════════════════
            # SUMMARY
            # ═══════════════════════════════════════════════════════════════
            print(f"\n{'#'*80}")
            print(f"# PIPELINE COMPLETE (SIMPLIFIED)")
            print(f"# Total atomic constraints: {len(atomic_texts)}")
            print(f"# Negated constraints collected: {len(all_negated_constraints) if all_negated_constraints else 0}")
            print(f"# After deduplication: {len(unique_negated)}")
            print(f"# After conflict validation: {len(valid_negated)}")
            print(f"# Valid constraints (before final dedup): {len(atomic_constraints)}")
            print(f"# Unique constraints (after final dedup): {len(unique_constraints)}")
            print(f"# Errors: {len(errors)}")
            print(f"# Warnings: {len(warnings)}")
            print(f"{'#'*80}\n")
            
            return ProcessingResult(
                success=len(unique_constraints) > 0,
                atomic_constraints=unique_constraints,
                original_input=input_text,
                processing_metadata={
                    "total_atomic_constraints": len(atomic_texts),
                    "valid_constraints": len(unique_constraints),
                    "duplicates_removed": len(atomic_constraints) - len(unique_constraints),
                    "conflicts_detected": len(conflict_result.get("conflicts", [])) if 'conflict_result' in locals() else 0,
                    "pipeline_version": "6.0_SIMPLIFIED",
                    "features": [
                        "smart_atomization",
                        "linear_flow",  # NEW!
                        "extract_after_validation",  # NEW!
                        "pre_validation_deduplication",  # NEW!
                        "integer_output",
                        "rule_based_validation",
                        "priority_validation",
                        "conflict_detection",
                        "conflict_handler_validation",
                        "csp_output_logging",
                        "priority_enforcement",
                        "deduplication",
                        "timeslot_objects",
                        "preference_type_support",
                        "min_confidence_scores",
                        "standardized_metadata"
                    ]
                },
                errors=errors,
                warnings=warnings
            )
        
        except Exception as e:
            error_msg = f"Pipeline error: {str(e)}"
            print(f"\n❌ CRITICAL ERROR: {error_msg}\n")
            return ProcessingResult(
                success=False,
                atomic_constraints=[],
                original_input=input_text,
                processing_metadata={},
                errors=[error_msg],
                warnings=[]
            )