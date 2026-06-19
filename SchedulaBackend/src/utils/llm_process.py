# src/utils/llm_process.py

import os
from typing import Dict, Any, Optional, Callable, Awaitable

from src.llm_pipeline import (
    ConstraintProcessingPipeline,
    OllamaLLM,
    UniversityLLM,
    CSPOutputLogger
)
from src.config import settings

# Type alias for stage update callback
StageUpdateCallback = Optional[Callable[[str], Awaitable[None]]]

# Global pipeline instance (lazy initialization)
_pipeline_instance: ConstraintProcessingPipeline | None = None


def _get_pipeline() -> ConstraintProcessingPipeline:
    """
    Get or create the constraint processing pipeline.
    Uses lazy initialization to avoid startup delays.
    """
    global _pipeline_instance
    
    if _pipeline_instance is None:
        provider = settings.llm_provider.lower()

        if provider == "university":
            print(f"Using University LLM Provider (Model: {settings.ollama_model})")
            llm = UniversityLLM(model=settings.ollama_model, base_url=settings.university_url)
        else:
            print(f"🦙 Using Ollama LLM Provider (Model: {settings.ollama_model})")
            llm = OllamaLLM(model=settings.ollama_model, base_url=settings.ollama_url)

        csp_logger = CSPOutputLogger()  # In-memory logger, won't write to file
        _pipeline_instance = ConstraintProcessingPipeline(llm, csp_logger)
    
    return _pipeline_instance


async def process_constraint(
        text: str,
        lecturer_id: int,
        semester_year: int,
        semester_number: int,
        skip_wrap_stage: bool = False,
        on_stage_update: StageUpdateCallback = None
) -> Dict[str, Any]:
    """
    Process natural language constraint text using the integrated LLM pipeline.
    
    This function directly invokes the constraint processing pipeline instead of
    making HTTP calls to a separate microservice.
    
    Args:
        text: The natural language constraint text to process
        lecturer_id: ID of the lecturer submitting the constraint
        semester_year: Year of the semester
        semester_number: Semester number (1-3)
        skip_wrap_stage: If True, skip WRAP stage (conflict resolution).
                        Used when editing to avoid checking conflicts with self.
        on_stage_update: Optional async callback for progress updates.
                        Called with stage name before each processing stage.
    
    Returns:
        Dict containing:
        - status: "success" or "error"
        - processing_time_seconds: Time taken to process
        - result: Contains lecturer_id, semester info, original_text, atomic_constraints, etc.
    
    Raises:
        Exception: If the pipeline fails to process the constraint
    """
    import time
    import logging
    
    logger = logging.getLogger(__name__)
    start_time = time.time()
    pipeline = _get_pipeline()
    
    # Process the constraint text through the pipeline with stage updates
    result = await pipeline.process(text, on_stage_update=on_stage_update)
    
    # WRAP Stage: Conflict resolution (skip if editing)
    if skip_wrap_stage:
        logger.info("⏭️ SKIPPING WRAP stage (edit mode - no conflict checking needed)")
    else:
        logger.info("🔄 WRAP stage would run here for conflict resolution (when implemented)")
        # TODO: WRAP stage implementation will go here
        pass
    
    processing_time = time.time() - start_time
    
    if not result.success:
        return {
            "status": "error",
            "processing_time_seconds": round(processing_time, 2),
            "errors": result.errors or ["Unknown error"],
            "result": {
                "lecturer_id": lecturer_id,
                "semester_year": semester_year,
                "semester_number": semester_number,
                "original_text": text,
                "atomic_constraints": [],
                "warnings": result.warnings,
                "errors": result.errors
            }
        }
    
    # Convert atomic constraints to response format
    atomic_constraints = []
    for c in result.atomic_constraints:
        atomic_constraints.append({
            "constraint_id": c.constraint_id,
            "type": c.constraint_type.value,
            "days": c.days,
            "time_slot": {
                "start_hour": c.time_slot.start_hour,
                "start_minute": c.time_slot.start_minute,
                "end_hour": c.time_slot.end_hour,
                "end_minute": c.time_slot.end_minute
            } if c.time_slot else None,
            "priority": c.priority,
            "confidence": c.confidence_score,
            "metadata": c.metadata,
            "original_text": c.original_text
        })
    
    return {
        "status": "success",
        "processing_time_seconds": round(processing_time, 2),
        "result": {
            "lecturer_id": lecturer_id,
            "semester_year": semester_year,
            "semester_number": semester_number,
            "original_text": text,
            "atomic_constraints": atomic_constraints,
            "warnings": result.warnings,
            "errors": result.errors
        }
    }
