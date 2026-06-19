"""
Processing result data model
"""
from dataclasses import dataclass
from typing import List, Dict, Any

from .atomic_constraint import AtomicConstraint


@dataclass
class ProcessingResult:
    """Result of the entire pipeline"""
    success: bool
    atomic_constraints: List[AtomicConstraint]
    original_input: str
    processing_metadata: Dict[str, Any]
    errors: List[str]
    warnings: List[str]
