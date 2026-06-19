"""Validators for cross-cutting business rules.

These guards run after pydantic shape validation and enforce semantic
contracts that pydantic alone cannot express (for example: a secretary may
edit an atomic constraint's hours but never change its `type`).
"""

from src.validators.structured_rules_validator import (
    StructuredRulesValidationError,
    StructuredRulesValidator,
    build_preview_text,
)

__all__ = [
    "StructuredRulesValidationError",
    "StructuredRulesValidator",
    "build_preview_text",
]
