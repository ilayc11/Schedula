"""Base model classes for consistent Pydantic configuration."""

from pydantic import BaseModel, ConfigDict


class SchedulaBaseModel(BaseModel):
    """Base model with shared configuration for all Schedula models.
    
    Automatically enables ORM mode for compatibility with database records.
    All domain models should inherit from this class for consistency.
    """
    model_config = ConfigDict(from_attributes=True)
