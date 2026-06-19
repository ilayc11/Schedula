"""
Enumerations for constraint system
"""
from enum import Enum


class ConstraintType(Enum):
    """Types of constraints"""
    BLOCK = "block"
    PREFERENCE = "preference"


class ConstraintPolarity(Enum):
    """Polarity of constraint"""
    NEGATIVE = "negative"
    POSITIVE = "positive"
