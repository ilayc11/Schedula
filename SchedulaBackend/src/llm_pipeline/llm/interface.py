"""
LLM interface abstraction
"""
from abc import ABC, abstractmethod


class LLMInterface(ABC):
    """Abstract interface for LLM calls"""
    
    @abstractmethod
    async def call(self, prompt: str, system_prompt: str) -> str:
        """Call the LLM with a prompt"""
        pass
