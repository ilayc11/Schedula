"""
Base class for all LLM processing stages
Provides common functionality for prompt loading and JSON parsing
"""
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

from ..llm.interface import LLMInterface


class BaseStage(ABC):
    """
    Base class for all LLM processing stages.
    
    Handles:
    - Loading prompts from text files
    - Prepending shared domain context
    - JSON response parsing with fallback strategies
    """
    
    def __init__(self, llm: LLMInterface, prompt_name: str):
        """
        Initialize stage with LLM and prompt name.
        
        Args:
            llm: LLM interface implementation
            prompt_name: Name of prompt file (without .txt extension)
        """
        self.llm = llm
        self.system_prompt = self._load_prompt(prompt_name)
    
    def _load_prompt(self, prompt_name: str) -> str:
        """
        Load prompt from file and prepend shared domain context.
        
        Args:
            prompt_name: Name of prompt file (e.g., 'clarification')
        
        Returns:
            Complete system prompt with domain context prepended
        """
        # Get the prompts directory path (relative to this file)
        base_dir = Path(__file__).parent.parent
        prompts_dir = base_dir / "prompts"
        
        # Load shared domain context
        domain_context_path = prompts_dir / "shared" / "domain_context.txt"
        try:
            with open(domain_context_path, 'r', encoding='utf-8') as f:
                domain_context = f.read().strip()
        except FileNotFoundError:
            print(f"Warning: Domain context file not found at {domain_context_path}")
            domain_context = ""
        
        # Load stage-specific prompt
        prompt_path = prompts_dir / f"{prompt_name}.txt"
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                stage_prompt = f.read().strip()
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Prompt file not found: {prompt_path}\n"
                f"Make sure {prompt_name}.txt exists in {prompts_dir}"
            )
        
        # Combine: domain context + stage prompt
        if domain_context:
            return f"{domain_context}\n\n{'='*80}\n\n{stage_prompt}"
        else:
            return stage_prompt
    
    def _extract_json(self, response: str) -> str:
        """
        Extract JSON from LLM response, handling common malformations.
        
        Args:
            response: Raw LLM response
        
        Returns:
            Extracted JSON string
        """
        # Remove markdown code fences
        response = re.sub(r'^```json\s*', '', response, flags=re.IGNORECASE)
        response = re.sub(r'^```\s*', '', response)
        response = response.replace('```', '').strip()
        
        # Try to extract JSON object or array
        json_match = re.search(r'[\[{][\s\S]*[\]}]', response)
        if json_match:
            return json_match.group(0)
        
        return response
    
    def _parse_json(self, response: str, default: Any = None) -> Any:
        """
        Parse JSON with multiple fallback strategies.
        
        Args:
            response: Raw LLM response
            default: Default value to return on parse failure
        
        Returns:
            Parsed JSON object or default value
        """
        # Extract JSON from response
        json_str = self._extract_json(response)
        
        # Strategy 1: Direct parse
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        
        # Strategy 2: Fix trailing commas
        try:
            fixed = re.sub(r',(\s*[}\]])', r'\1', json_str)
            return json.loads(fixed)
        except json.JSONDecodeError:
            pass
        
        # Strategy 3: Extract first complete object/array
        try:
            # Find first { or [
            start = min(
                (json_str.find('{') if '{' in json_str else len(json_str)),
                (json_str.find('[') if '[' in json_str else len(json_str))
            )
            if start < len(json_str):
                # Use simple bracket counting
                brackets = {'(': 0, '[': 0, '{': 0}
                closing = {'(': ')', '[': ']', '{': '}'}
                opener = json_str[start]
                brackets[opener] = 1
                
                for i in range(start + 1, len(json_str)):
                    char = json_str[i]
                    if char in brackets:
                        brackets[char] += 1
                    elif char in closing.values():
                        for open_char, close_char in closing.items():
                            if char == close_char:
                                brackets[open_char] -= 1
                                if brackets[opener] == 0:
                                    return json.loads(json_str[start:i+1])
        except (json.JSONDecodeError, ValueError, KeyError):
            pass
        
        # All strategies failed
        if default is not None:
            print(f"⚠️  JSON parsing failed, using default value")
            print(f"   Response (first 200 chars): {response[:200]}")
            return default
        else:
            raise json.JSONDecodeError(
                f"Failed to parse JSON from response: {response[:200]}...",
                response, 0
            )
    
    @abstractmethod
    async def process(self, *args, **kwargs) -> Any:
        """
        Process input through this stage.
        Must be implemented by subclasses.
        """
        pass

