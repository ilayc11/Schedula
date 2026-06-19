"""
Ollama LLM provider implementation
"""
import re
import aiohttp
from .interface import LLMInterface
from ...config import settings


class OllamaLLM(LLMInterface):
    """Ollama implementation"""
    
    def __init__(self, model: str = None, base_url: str = None, timeout: int = 300):
        self.model = model or settings.ollama_model
        self.base_url = base_url or settings.ollama_url
        self.timeout = aiohttp.ClientTimeout(total=timeout)
    
    async def call(self, prompt: str, system_prompt: str) -> str:
        """Call Ollama API"""
        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "system": system_prompt,
                "stream": False,
                "options": {
                    "temperature": 0,
                    "top_p": 0.9
                }
            }
            
            try:
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json=payload
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(f"Ollama API Error {response.status}: {error_text}")
                        
                    result = await response.json()
                    response_text = result.get("response", "")
                    # Clean up provider-specific artifacts (e.g., DeepSeek thinking blocks)
                    response_text = re.sub(r'<think>.*?</think>', '', response_text, flags=re.DOTALL).strip()
                    return response_text
            except Exception as e:
                print(f"❌ Ollama Connection Error: {e}")
                raise # Re-raise so the pipeline knows it failed
