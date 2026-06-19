"""
LLM providers package
"""
from .interface import LLMInterface
from .ollama_provider import OllamaLLM
from .university_provider import UniversityLLM

__all__ = ['LLMInterface', 'OllamaLLM', 'UniversityLLM']
