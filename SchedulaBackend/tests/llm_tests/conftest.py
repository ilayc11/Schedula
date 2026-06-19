"""
Shared test fixtures for the LLM pipeline tests
"""
import os
import pytest
from httpx import AsyncClient, ASGITransport
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from src.main import app
from src.llm_pipeline import OllamaLLM, UniversityLLM, CSPOutputLogger, ConstraintProcessingPipeline
from src.llm_pipeline.llm.groq_provider import GroqLLM
from src.llm_pipeline.processing_stages import (
    AtomizationStage,
    ClassificationStage,
    NegationStage,
    ExtractionStage
)
from src.llm_pipeline.constraint_validation.rule_validator import RuleBasedValidator

from src.config import settings

# Test constants
TEST_LECTURER_ID = 999
TEST_SECRETARY_ID = 888
# OLLAMA settings are now loaded from src.config.settings
# You can override them via environment variables if needed for specific tests


# --- Auth Override Middleware for Tests ---
class TestAuthMiddleware(BaseHTTPMiddleware):
    """Middleware that bypasses JWT validation and injects test user context."""
    
    async def dispatch(self, request: Request, call_next):
        # Inject test user context into request.state
        # Determine role based on path
        if request.url.path.startswith("/lecturer"):
            request.state.user_internal_id = TEST_LECTURER_ID
            request.state.user_role = "L"
        elif request.url.path.startswith("/secretary"):
            request.state.user_internal_id = TEST_SECRETARY_ID
            request.state.user_role = "S"
        
        request.state.user_payload = {
            "sub": str(request.state.user_internal_id) if hasattr(request.state, "user_internal_id") else None,
            "role": request.state.user_role if hasattr(request.state, "user_role") else None
        }
        
        return await call_next(request)


# Replace AuthenticationMiddleware with TestAuthMiddleware for testing
from src.middleware.auth import AuthenticationMiddleware
from starlette.middleware import Middleware

# Rebuild middleware stack with test auth middleware instead of production
new_middleware = []
for middleware in app.user_middleware:
    if middleware.cls == AuthenticationMiddleware:
        # Replace with test middleware
        new_middleware.append(Middleware(TestAuthMiddleware))
    else:
        new_middleware.append(middleware)

app.user_middleware = new_middleware


# --- Fixtures ---

@pytest.fixture
def llm():
    """Create an LLM instance for testing based on configured provider."""
    # Uses defaults from settings (which reads env vars)
    provider = settings.llm_provider.lower()
    if provider == "groq":
        return GroqLLM()
    if provider == "university":
        return UniversityLLM()
    else:
        return OllamaLLM()


@pytest.fixture
def groq_llm():
    """Create a Groq LLM instance for testing."""
    # Uses defaults from settings (which reads env vars)
    return GroqLLM()


@pytest.fixture
def atomization_stage(llm):
    """Create an atomization stage instance."""
    return AtomizationStage(llm)


@pytest.fixture
def classification_stage(llm):
    """Create a classification stage instance."""
    return ClassificationStage(llm)


@pytest.fixture
def negation_stage(llm):
    """Create a negation stage instance."""
    return NegationStage(llm)


@pytest.fixture
def extraction_stage(llm):
    """Create an extraction stage instance."""
    return ExtractionStage(llm)


@pytest.fixture
def validator():
    """Create a rule-based validator instance (no LLM needed)."""
    return RuleBasedValidator()


@pytest.fixture
def csp_logger():
    """Create a CSP output logger instance."""
    return CSPOutputLogger()


@pytest.fixture
def pipeline(llm, csp_logger):
    """Create a full pipeline instance."""
    return ConstraintProcessingPipeline(llm, csp_logger)


@pytest.fixture
async def async_client():
    """Create an async HTTP client for API tests."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=120.0) as client:
        yield client

