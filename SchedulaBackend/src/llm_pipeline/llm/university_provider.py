"""
University LLM provider implementation.
Uses an Ollama-compatible endpoint hosted by the university.
"""
import re

import aiohttp

from .interface import LLMInterface
from ...config import settings


class UniversityLLM(LLMInterface):
    """University-hosted Ollama-compatible implementation."""

    def __init__(self, model: str = None, base_url: str = None, timeout: int = 300):
        self.model = model or settings.ollama_model
        self.base_url = (base_url or settings.university_url).rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    async def call(self, prompt: str, system_prompt: str) -> str:
        """Call the university Ollama-compatible API."""
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
                "options": {
                    "temperature": 0,
                    "top_p": 0.9,
                },
            }

            try:
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    ssl=settings.university_verify_ssl,
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"University API Error {response.status}: {error_text}")

                    result = await response.json()
                    response_text = result.get("response", "")
                    response_text = re.sub(r"<think>.*?</think>", "", response_text, flags=re.DOTALL).strip()
                    return response_text
            except Exception as e:
                print(f"University provider connection error: {e}")
                raise
